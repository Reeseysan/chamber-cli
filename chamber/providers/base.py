from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Awaitable

import httpx


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    @abstractmethod
    async def stream_completion(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None] | None],
    ) -> str:
        """Stream a completion, calling on_token for each chunk. Returns full text."""
        ...

    @abstractmethod
    async def completion(self, system: str, messages: list[dict]) -> str:
        """Non-streaming completion. Returns full text."""
        ...

    @abstractmethod
    async def json_completion(self, system: str, messages: list[dict]) -> str:
        """Completion that returns JSON. Returns raw JSON string."""
        ...

    async def close(self) -> None:
        """Close any resources (e.g. HTTP client). Override if needed."""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """Base class for providers using the OpenAI-compatible chat/completions API.
    
    Handles the common SSE streaming parser, connection pooling, and request format.
    Subclasses only need to implement __init__, _base_url, _headers, and optionally
    _json_completion_extra_body for provider-specific JSON mode settings.
    """

    model: str
    _client: httpx.AsyncClient | None

    def __init__(self):
        self._client = None

    def _client_kwargs(self) -> dict:
        """Override to add proxy, custom timeout, etc."""
        return {"timeout": 120}

    @abstractmethod
    def _base_url(self) -> str:
        """Return the base URL (e.g. 'https://api.openai.com')."""
        ...

    @abstractmethod
    def _headers(self) -> dict:
        """Return request headers (auth, content-type, etc.)."""
        ...

    def _json_completion_extra_body(self) -> dict:
        """Extra body params for json_completion (e.g. response_format). Override per provider."""
        return {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and reuse a single httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(**self._client_kwargs())
        return self._client

    async def close(self) -> None:
        """Close the persistent HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def completion(self, system: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        client = await self._get_client()
        resp = await client.post(
            f"{self._base_url()}/v1/chat/completions",
            headers=self._headers(),
            json={"model": self.model, "messages": full_messages, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def stream_completion(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None] | None],
    ) -> str:
        import json as json_mod
        full_messages = [{"role": "system", "content": system}] + messages
        full_text = ""
        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self._base_url()}/v1/chat/completions",
            headers=self._headers(),
            json={"model": self.model, "messages": full_messages, "stream": True},
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                chunk = json_mod.loads(payload)
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    full_text += token
                    result = on_token(token)
                    if result is not None:
                        await result
        return full_text

    async def json_completion(self, system: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        full_messages[0]["content"] += "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        body = {
            "model": self.model,
            "messages": full_messages,
            "stream": False,
        }
        body.update(self._json_completion_extra_body())
        client = await self._get_client()
        resp = await client.post(
            f"{self._base_url()}/v1/chat/completions",
            headers=self._headers(),
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
