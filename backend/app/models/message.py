"""
Open-Brain Backend — Message Model

Stores individual messages within a conversation (user prompts and AI responses).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Message(Base):
    """Chat message model — represents a single turn in a conversation."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Either 'user' or 'assistant'.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    provider_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="The AI provider that generated this response (e.g. 'claude-3-opus').",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Estimated token count for this message.",
    )
    is_partial: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        doc="True if the response was cut off due to a client disconnect.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, partial={self.is_partial})>"
