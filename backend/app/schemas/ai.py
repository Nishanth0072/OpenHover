"""
Open-Brain Backend — AI Schemas

Pydantic models for AI chat and characters endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """AI chat request payload."""

    chat_id: Optional[str] = Field(
        None,
        description="Existing conversation ID to continue. If omitted, a new conversation is created.",
        examples=["abc123"],
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="The user's message/prompt to send to the AI.",
        examples=["Write a Python script to sort a list."],
    )
    provider: str = Field(
        default="claude",
        description="AI provider to use: 'claude', 'openai', or 'ollama'.",
        examples=["claude"],
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override (e.g. 'claude-sonnet-4-20250514', 'gpt-4o').",
    )
    character_id: Optional[str] = Field(
        None,
        description="Optional character ID to use a specific AI persona's system prompt.",
        examples=["einstein"],
    )


class CharacterSchema(BaseModel):
    """AI character definition."""

    id: str = Field(..., description="Unique character identifier.")
    name: str = Field(..., description="Display name of the character.")
    description: str = Field(..., description="Short description of the character's personality.")
    system_prompt: str = Field(..., description="System prompt that defines the character's behavior.")
    avatar: Optional[str] = Field(None, description="URL or path to the character's avatar image.")


class ChatStartResponse(BaseModel):
    """Response when a new chat is initiated (non-streaming metadata)."""

    chat_id: str
    title: str
