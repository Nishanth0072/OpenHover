"""
Open-Brain Backend — Claude (Anthropic) Provider Adapter

Implements streaming chat completion using the Anthropic Messages API.
"""

import json
from typing import AsyncGenerator

import httpx
from loguru import logger

from app.config import settings
from app.providers.base import AIProvider


class ClaudeProvider(AIProvider):
    """Anthropic Claude API adapter."""

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @property
    def provider_name(self) -> str:
        return "claude"

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the Claude API."""
        model = model or self.DEFAULT_MODEL

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Extract system prompt from messages (Anthropic requires it as a top-level field)
        system_prompt = next((m["content"] for m in messages if m["role"] == "system"), None)
        filtered_messages = [m for m in messages if m["role"] != "system"]

        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": filtered_messages,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with self._client.stream(
                "POST",
                self.ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(f"Claude API error {response.status_code}: {error_body}")
                    yield f"[Error: Claude API returned status {response.status_code}]"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix

                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type", "")

                        if event_type == "message_stop":
                            break

                        if event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text

                    except json.JSONDecodeError:
                        continue

        except httpx.HTTPError as e:
            logger.error(f"Claude HTTP error: {e}")
            yield f"[Error: Failed to connect to Claude API: {e}]"

    async def close(self) -> None:
        """Close the httpx client."""
        await self._client.aclose()
