import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from app.services.ai_service import stream_ai_response
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

from typing import Optional

class ExplainParams(BaseModel):
    text: str
    context: str
    url: str
    title: str
    provider: Optional[str] = None
    model: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatParams(BaseModel):
    messages: list[ChatMessage]
    context: str
    url: str
    title: str
    provider: Optional[str] = None
    model: Optional[str] = None

@router.post("/api/explain")
async def explain_endpoint(
    params: ExplainParams,
    current_user: User = Depends(get_current_user),
):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful browser-overlay reading assistant. Explain the hovered text clearly and concisely using the surrounding context. If the text is ambiguous out of context, note the ambiguity."
        },
        {
            "role": "user",
            "content": f"Hovered text: \"{params.text}\"\nSurrounding context: \"{params.context}\"\nPage title: \"{params.title}\"\nPage URL: \"{params.url}\""
        }
    ]
    
    async def event_generator():
        try:
            # Determine provider based on configuration or request
            from app.config import settings
            if params.provider in ["openai", "ollama", "anthropic", "claude"]:
                provider = "claude" if params.provider == "anthropic" else params.provider
            else:
                provider = "openai" if settings.openai_api_key and settings.openai_api_key != "sk-your-key-here" else "ollama"
            async for chunk in stream_ai_response(provider, messages, model=params.model):
                yield {"data": json.dumps({"type": "chunk", "content": chunk})}
            yield {"data": json.dumps({"type": "done"})}
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "message": str(e)})}
            
    return EventSourceResponse(event_generator())

@router.post("/api/chat")
async def chat_endpoint(
    params: ChatParams,
    current_user: User = Depends(get_current_user),
):
    messages = [
        {
            "role": "system",
            "content": f"You are a helpful browser-overlay reading assistant. Context:\n{params.context}\nPage title: {params.title}\nPage URL: {params.url}"
        }
    ]
    for msg in params.messages:
        messages.append({"role": msg.role, "content": msg.content})
        
    async def event_generator():
        try:
            from app.config import settings
            if params.provider in ["openai", "ollama", "anthropic", "claude"]:
                provider = "claude" if params.provider == "anthropic" else params.provider
            else:
                provider = "openai" if settings.openai_api_key and settings.openai_api_key != "sk-your-key-here" else "ollama"
            async for chunk in stream_ai_response(provider, messages, model=params.model):
                yield {"data": json.dumps({"type": "chunk", "content": chunk})}
            yield {"data": json.dumps({"type": "done"})}
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "message": str(e)})}
            
    return EventSourceResponse(event_generator())
