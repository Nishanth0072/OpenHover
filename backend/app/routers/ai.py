"""
Open-Brain Backend — AI Router

Endpoints: POST /ai/chat (SSE streaming), GET /ai/characters.
"""

import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from loguru import logger

from app.database import get_db
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.ai import ChatRequest, CharacterSchema
from app.schemas.auth import ErrorResponse
from app.services.ai_service import stream_ai_response, load_characters
from app.services.chat_service import get_or_create_conversation, add_message
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter()


@router.post(
    "/chat",
    summary="AI Chat (Streaming)",
    description=(
        "Sends a prompt to the selected AI provider and streams the response "
        "via Server-Sent Events (SSE). If chat_id is provided, appends to that "
        "conversation; otherwise creates a new one."
    ),
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def ai_chat(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """
    Core AI chat endpoint with SSE streaming.

    Implements:
    - Rate limiting via Redis
    - Conversation get-or-create
    - User message persistence
    - SSE streaming from AI provider
    - Partial save on client disconnect (edge cases plan)
    - Full response save on completion
    """
    # Rate limit check
    allowed = await check_rate_limit(redis_client, current_user.id, "ai_chat")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI chat rate limit exceeded. Please wait before sending another message.",
        )

    # Validate provider
    valid_providers = {"claude", "openai", "ollama"}
    if payload.provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Choose from: {', '.join(valid_providers)}",
        )

    # Get or create conversation
    title = payload.prompt[:50] + "..." if len(payload.prompt) > 50 else payload.prompt
    conversation = await get_or_create_conversation(
        db, current_user.id, payload.chat_id, title
    )

    # Save user message
    await add_message(db, conversation.id, "user", payload.prompt)
    await db.commit()

    # Build message history for the AI provider
    from app.services.chat_service import get_conversation_history

    conv_with_history = await get_conversation_history(db, current_user.id, conversation.id)
    messages = []

    # Prepend character system prompt if a character_id is provided
    if payload.character_id:
        characters = load_characters()
        character = next((c for c in characters if c.id == payload.character_id), None)
        if character:
            messages.append({"role": "system", "content": character.system_prompt})

    if conv_with_history and conv_with_history.messages:
        for msg in conv_with_history.messages:
            messages.append({"role": msg.role, "content": msg.content})
    else:
        messages.append({"role": "user", "content": payload.prompt})

    async def event_generator():
        """SSE event generator with partial-save on disconnect."""
        accumulated_response = []
        is_complete = False

        try:
            # Send chat_id as the first event so the client knows which conversation this is
            yield {
                "event": "chat_start",
                "data": json.dumps({
                    "chat_id": str(conversation.id),
                    "title": conversation.title,
                }),
            }

            # Stream AI response
            async for chunk in stream_ai_response(
                payload.provider, messages, payload.model
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.warning(f"Client disconnected during stream for chat {conversation.id}")
                    break

                accumulated_response.append(chunk)
                yield {
                    "event": "chunk",
                    "data": json.dumps({"text": chunk}),
                }

            is_complete = not await request.is_disconnected()

            # Send completion event
            if is_complete:
                yield {
                    "event": "done",
                    "data": json.dumps({"status": "complete"}),
                }

        finally:
            # Save the AI response (full or partial) to the database
            full_response = "".join(accumulated_response)
            if full_response:
                try:
                    # Use a new session for the background save
                    from app.database import async_session_factory

                    async with async_session_factory() as save_db:
                        await add_message(
                            save_db,
                            conversation.id,
                            "assistant",
                            full_response,
                            provider_used=payload.provider,
                            is_partial=not is_complete,
                        )
                        await save_db.commit()

                    if not is_complete:
                        logger.info(
                            f"Saved PARTIAL AI response ({len(full_response)} chars) "
                            f"for chat {conversation.id}"
                        )
                    else:
                        logger.info(
                            f"Saved complete AI response ({len(full_response)} chars) "
                            f"for chat {conversation.id}"
                        )
                except Exception as e:
                    logger.error(f"Failed to save AI response: {e}")

    return EventSourceResponse(event_generator())


@router.get(
    "/characters",
    response_model=list[CharacterSchema],
    summary="List AI Characters",
    description="Returns a list of available AI characters that users can chat with.",
)
async def get_characters(
    current_user: User = Depends(get_current_user),
):
    """Return the list of available AI characters."""
    defaults = load_characters()
    return defaults + CUSTOM_CHARACTERS


@router.post("/chat/stop")
async def stop_chat_generation(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    chat_id = payload.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id is required.")
    return {"message": "Generation stopped."}


@router.post("/chat/{message_id}/feedback")
async def record_chat_feedback(
    message_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    rating = payload.get("rating")
    if rating not in [1, -1]:
        raise HTTPException(status_code=400, detail="rating must be 1 or -1.")
    return {"message": "Feedback recorded."}


@router.get("/providers")
async def get_providers(
    current_user: User = Depends(get_current_user),
):
    return [
        {
            "name": "openai",
            "models": ["gpt-4o", "gpt-4-turbo"],
            "available": True
        },
        {
            "name": "claude",
            "models": ["claude-sonnet-4-20250514"],
            "available": True
        },
        {
            "name": "ollama",
            "models": ["gemma3:4b"],
            "available": True
        }
    ]


# Custom in-memory list for user personas
CUSTOM_CHARACTERS = []

@router.post("/characters", response_model=CharacterSchema)
async def create_custom_character(
    payload: CharacterSchema,
    current_user: User = Depends(get_current_user),
):
    CUSTOM_CHARACTERS.append(payload)
    return payload


@router.patch("/characters/{id}", response_model=CharacterSchema)
async def update_custom_character(
    id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    for c in CUSTOM_CHARACTERS:
        if c.id == id:
            if "name" in payload:
                c.name = payload["name"]
            if "description" in payload:
                c.description = payload["description"]
            if "system_prompt" in payload:
                c.system_prompt = payload["system_prompt"]
            if "avatar" in payload:
                c.avatar = payload["avatar"]
            return c
            
    # If not found in custom, search in default loaded ones and return a copy with edits
    defaults = load_characters()
    character = next((c for c in defaults if c.id == id), None)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found.")
        
    updated = CharacterSchema(
        id=character.id,
        name=payload.get("name", character.name),
        description=payload.get("description", character.description),
        system_prompt=payload.get("system_prompt", character.system_prompt),
        avatar=payload.get("avatar", character.avatar)
    )
    CUSTOM_CHARACTERS.append(updated)
    return updated


@router.delete("/characters/{id}")
async def delete_custom_character(
    id: str,
    current_user: User = Depends(get_current_user),
):
    global CUSTOM_CHARACTERS
    for c in CUSTOM_CHARACTERS:
        if c.id == id:
            CUSTOM_CHARACTERS = [x for x in CUSTOM_CHARACTERS if x.id != id]
            return {"message": "Character persona deleted."}
    raise HTTPException(status_code=404, detail="Character not found.")
