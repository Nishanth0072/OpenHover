"""
Open-Brain Backend — Chat Service

Business logic for conversation CRUD operations.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message


async def create_conversation(
    db: AsyncSession,
    user_id: str,
    title: str = "New Chat",
) -> Conversation:
    """Create a new conversation for a user."""
    conversation = Conversation(
        user_id=user_id,
        title=title,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def list_conversations(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int]:
    """
    List conversations for a user with pagination.

    Returns (conversations, total_count).
    """
    # Count total
    count_query = select(func.count()).select_from(Conversation).where(
        Conversation.user_id == user_id
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    query = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    conversations = list(result.scalars().all())

    return conversations, total


async def get_conversation_history(
    db: AsyncSession,
    user_id: str,
    chat_id: str,
) -> Optional[Conversation]:
    """
    Get a conversation with all its messages.

    Returns None if the conversation doesn't exist or doesn't belong to the user.
    """
    query = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == chat_id,
            Conversation.user_id == user_id,
        )
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def delete_conversation(
    db: AsyncSession,
    user_id: str,
    chat_id: str,
) -> bool:
    """
    Delete a conversation and all its messages.

    Returns True if deleted, False if not found.
    """
    # Verify ownership
    query = select(Conversation).where(
        Conversation.id == chat_id,
        Conversation.user_id == user_id,
    )
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        return False

    await db.delete(conversation)
    await db.flush()
    return True


async def add_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    provider_used: Optional[str] = None,
    token_count: Optional[int] = None,
    is_partial: bool = False,
) -> Message:
    """Add a message to a conversation."""
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        provider_used=provider_used,
        token_count=token_count,
        is_partial=is_partial,
    )
    db.add(message)

    # Update conversation's updated_at
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return message


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: str,
    chat_id: Optional[str],
    title: str = "New Chat",
) -> Conversation:
    """
    Get an existing conversation or create a new one.

    If chat_id is provided, fetches it (verifying ownership).
    If chat_id is None, creates a new conversation.
    """
    if chat_id:
        query = select(Conversation).where(
            Conversation.id == chat_id,
            Conversation.user_id == user_id,
        )
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()
        if conversation:
            return conversation

    # Create new conversation
    return await create_conversation(db, user_id, title)
