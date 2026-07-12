"""
Open-Brain Backend — OpenAI Provider Adapter

Implements streaming chat completion using the OpenAI Chat Completions API.
"""

import json
from typing import AsyncGenerator

import httpx
from loguru import logger

from app.config import settings
from app.providers.base import AIProvider


class OpenAIProvider(AIProvider):
    """OpenAI API adapter."""

    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the OpenAI API."""
        model = model or self.DEFAULT_MODEL

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST",
                self.OPENAI_API_URL,
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(f"OpenAI API error {response.status_code}: {error_body}")
                    yield f"[Error: OpenAI API returned status {response.status_code}]"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

        except httpx.HTTPError as e:
            logger.error(f"OpenAI HTTP error: {e}")
            yield f"[Error: Failed to connect to OpenAI API: {e}]"

    async def close(self) -> None:
        """Close the httpx client."""
        await self._client.aclose()
