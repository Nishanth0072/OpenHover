"""
Open-Brain Backend — Ollama Provider Adapter

Implements streaming chat completion using the Ollama API.
"""

import json
from typing import AsyncGenerator

import httpx
from loguru import logger

from app.config import settings
from app.providers.base import AIProvider


class OllamaProvider(AIProvider):
    """Ollama API adapter (local or cloud)."""

    DEFAULT_MODEL = "gemma3:4b"

    def __init__(self):
        base_url = settings.ollama_base_url or "http://localhost:11434"
        self._base_url = base_url.rstrip("/")
        headers = {}
        if settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the Ollama API."""
        model = model or self.DEFAULT_MODEL

        url = f"{self._base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST",
                url,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(f"Ollama API error {response.status_code}: {error_body}")
                    yield f"[Error: Ollama API returned status {response.status_code}]"
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        message = data.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield content

                        # Check if stream is done
                        if data.get("done", False):
                            break

                    except json.JSONDecodeError:
                        continue

        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            yield f"[Error: Failed to connect to Ollama API: {e}]"

    async def close(self) -> None:
        """Close the httpx client."""
        await self._client.aclose()
