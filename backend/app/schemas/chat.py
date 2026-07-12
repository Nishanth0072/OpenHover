"""
Open-Brain Backend — Chat Schemas

Pydantic models for chat/conversation request/response validation.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ConversationListItem(BaseModel):
    """Single conversation in a list view."""

    chat_id: str = Field(..., alias="id")
    title: str
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class MessageSchema(BaseModel):
    """Single message in a conversation."""

    id: str
    role: str = Field(..., description="Either 'user' or 'assistant'.")
    content: str
    provider_used: Optional[str] = None
    token_count: Optional[int] = None
    is_partial: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationHistoryResponse(BaseModel):
    """Full conversation with messages."""

    chat_id: str
    title: str
    messages: list[MessageSchema]
    created_at: datetime
    updated_at: datetime


class PaginatedConversationsResponse(BaseModel):
    """Paginated list of conversations."""

    conversations: list[ConversationListItem]
    total: int
    page: int
    page_size: int
    has_next: bool
