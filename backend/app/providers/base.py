"""
Open-Brain Backend — Abstract AI Provider

Base class for all AI provider adapters. Implements the provider-adapter pattern
so adding new providers only requires subclassing this.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator


class AIProvider(ABC):
    """Abstract base class for AI provider adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. 'claude', 'openai')."""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Optional model override.

        Yields:
            Text chunks as they arrive from the provider.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up any HTTP clients or connections."""
        ...
