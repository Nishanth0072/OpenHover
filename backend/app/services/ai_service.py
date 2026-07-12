"""
Open-Brain Backend — AI Service

Orchestrates AI provider selection, streaming, and partial-save on disconnect.
"""

import json
import os
from typing import AsyncGenerator, Optional

from loguru import logger

from app.providers.base import AIProvider
from app.providers.claude import ClaudeProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.ollama import OllamaProvider
from app.schemas.ai import CharacterSchema


# Provider instances (lazy-initialized)
_providers: dict[str, AIProvider] = {}


def get_provider(provider_name: str) -> AIProvider:
    """
    Factory: return an AI provider adapter by name.

    Lazily initializes providers on first use.
    """
    if provider_name not in _providers:
        if provider_name == "claude":
            _providers[provider_name] = ClaudeProvider()
        elif provider_name == "openai":
            _providers[provider_name] = OpenAIProvider()
        elif provider_name == "ollama":
            _providers[provider_name] = OllamaProvider()
        else:
            raise ValueError(f"Unknown AI provider: {provider_name}")

    return _providers[provider_name]


async def stream_ai_response(
    provider_name: str,
    messages: list[dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream an AI response using the specified provider.

    Yields text chunks as they arrive.
    """
    provider = get_provider(provider_name)
    logger.info(f"Streaming AI response via {provider.provider_name} (model: {model or 'default'})")

    async for chunk in provider.stream_chat(messages, model):
        yield chunk


def load_characters() -> list[CharacterSchema]:
    """
    Load AI characters from the characters.json config file.

    Returns a list of CharacterSchema objects.
    """
    # Look for characters.json in the data directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    characters_path = os.path.join(base_dir, "data", "characters.json")

    try:
        with open(characters_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [CharacterSchema(**char) for char in data]
    except FileNotFoundError:
        logger.warning(f"Characters file not found at {characters_path}, using defaults")
        return _default_characters()
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error loading characters: {e}")
        return _default_characters()


def _default_characters() -> list[CharacterSchema]:
    """Return default characters if the config file is missing."""
    return [
        CharacterSchema(
            id="default",
            name="Open-Brain Assistant",
            description="A helpful, knowledgeable AI assistant.",
            system_prompt="You are Open-Brain, a helpful and knowledgeable AI assistant. Be concise, accurate, and friendly.",
        ),
    ]


async def cleanup_providers() -> None:
    """Close all active provider connections."""
    for provider in _providers.values():
        await provider.close()
    _providers.clear()
