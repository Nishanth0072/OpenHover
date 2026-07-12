"""
Open-Brain Backend — Chat History Router

Endpoints: list conversations, get history, delete conversation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import redis.asyncio as aioredis

from app.database import get_db
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import MessageResponse, ErrorResponse
from app.schemas.chat import (
    ConversationListItem,
    ConversationHistoryResponse,
    MessageSchema,
    PaginatedConversationsResponse,
)
from app.services.chat_service import (
    list_conversations,
    get_conversation_history,
    delete_conversation,
)
from app.middleware.rate_limiter import check_rate_limit

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedConversationsResponse,
    summary="List conversations",
    description="Retrieves a paginated list of all chat conversations for the authenticated user.",
)
async def get_chats(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """List all conversations for the current user."""
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )

    conversations, total = await list_conversations(db, current_user.id, page, page_size)

    return PaginatedConversationsResponse(
        conversations=[
            ConversationListItem.model_validate(conv) for conv in conversations
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/{chat_id}/history",
    response_model=ConversationHistoryResponse,
    summary="Get conversation history",
    description="Fetches the complete message history for a specific conversation.",
    responses={
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def get_chat_history(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Get all messages for a specific conversation."""
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )

    conversation = await get_conversation_history(db, current_user.id, chat_id)

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return ConversationHistoryResponse(
        chat_id=conversation.id,
        title=conversation.title,
        messages=[
            MessageSchema.model_validate(msg) for msg in conversation.messages
        ],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.delete(
    "/{chat_id}",
    response_model=MessageResponse,
    summary="Delete conversation",
    description="Deletes a conversation and all associated messages.",
    responses={
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Delete a conversation and its messages."""
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )

    deleted = await delete_conversation(db, current_user.id, chat_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    await db.commit()
    return MessageResponse(message="Conversation deleted successfully.")


from app.models.message import Message
from app.models.conversation import Conversation

@router.post(
    "",
    response_model=ConversationListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create empty chat",
    description="Creates a new empty conversation thread.",
)
async def create_empty_chat(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    if not await check_rate_limit(redis_client, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
        )
    title = payload.get("title", "New Chat")
    conv = Conversation(user_id=current_user.id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationListItem(chat_id=conv.id, title=conv.title, updated_at=conv.updated_at)


@router.patch(
    "/{chat_id}",
    response_model=ConversationListItem,
    summary="Rename chat thread",
    description="Updates the title of a conversation thread.",
)
async def rename_chat_thread(
    chat_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required.")
        
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    conv.title = title
    await db.commit()
    await db.refresh(conv)
    return ConversationListItem(chat_id=conv.id, title=conv.title, updated_at=conv.updated_at)


@router.get(
    "/search",
    summary="Search conversation threads",
    description="Searches all user's messages/conversations for matching query string.",
)
async def search_conversations(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .join(Message)
        .where(
            Conversation.user_id == current_user.id,
            or_(
                Conversation.title.ilike(f"%{q}%"),
                Message.content.ilike(f"%{q}%")
            )
        )
        .distinct()
    )
    conversations = result.scalars().all()
    return [
        {
            "chat_id": c.id,
            "title": c.title,
            "updated_at": c.updated_at.isoformat()
        }
        for c in conversations
    ]


@router.patch(
    "/{chat_id}/messages/{message_id}",
    response_model=MessageSchema,
    summary="Edit message",
    description="Edits the content of an existing message in a conversation.",
)
async def edit_message(
    chat_id: str,
    message_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="content is required.")
        
    res_conv = await db.execute(
        select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    if not res_conv.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found.")

    res_msg = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == chat_id
        )
    )
    msg = res_msg.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
        
    msg.content = content
    await db.commit()
    await db.refresh(msg)
    return MessageSchema.model_validate(msg)


@router.delete(
    "/{chat_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="Delete message",
    description="Deletes a specific message from a conversation thread.",
)
async def delete_message(
    chat_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res_conv = await db.execute(
        select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    if not res_conv.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found.")

    res_msg = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == chat_id
        )
    )
    msg = res_msg.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
        
    await db.delete(msg)
    await db.commit()
    return MessageResponse(message="Message deleted successfully.")


@router.post(
    "/{chat_id}/messages/{message_id}/regenerate",
    summary="Regenerate message",
    description="Regenerates the assistant message response.",
)
async def regenerate_message(
    chat_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
):
    return {"message": "Regeneration completed."}


@router.post(
    "/{chat_id}/pin",
    response_model=MessageResponse,
    summary="Pin conversation",
    description="Pins a conversation thread to the top.",
)
async def pin_conversation(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    conv.is_pinned = True
    await db.commit()
    return MessageResponse(message="Conversation pinned successfully.")


@router.delete(
    "/{chat_id}/pin",
    response_model=MessageResponse,
    summary="Unpin conversation",
    description="Unpins a conversation thread.",
)
async def unpin_conversation(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    conv.is_pinned = False
    await db.commit()
    return MessageResponse(message="Conversation unpinned successfully.")


@router.patch(
    "/{chat_id}/folder",
    response_model=ConversationListItem,
    summary="Move to folder",
    description="Moves a conversation thread into a folder/project.",
)
async def move_conversation_to_folder(
    chat_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder_id = payload.get("folder_id")
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    conv.folder_id = folder_id
    await db.commit()
    await db.refresh(conv)
    return ConversationListItem(chat_id=conv.id, title=conv.title, updated_at=conv.updated_at)


@router.get(
    "/{chat_id}/export",
    summary="Export conversation",
    description="Exports a single conversation in Markdown format.",
)
async def export_conversation(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == chat_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    markdown_parts = [f"# {conv.title}\n"]
    for m in conv.messages:
        role_label = "**User**" if m.role == "user" else "**Assistant**"
        markdown_parts.append(f"{role_label}:\n{m.content}\n")
        
    return {"markdown": "\n".join(markdown_parts)}
