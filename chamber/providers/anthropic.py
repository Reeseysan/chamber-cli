from __future__ import annotations

import json
import os
from typing import Callable, Awaitable

import httpx

from chamber.providers.base import LLMProvider
from chamber.providers import register_provider


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider (api.anthropic.com).
    
    Does not extend OpenAICompatibleProvider because Anthropic uses
    a different message format (system as top-level param, content_block_delta events).
    Still uses connection pooling via a persistent httpx client.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        proxy: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("CHAMBER_ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set CHAMBER_ANTHROPIC_API_KEY or pass --provider ollama for local mode."
            )
        self.model = model or "claude-sonnet-4-20250514"
        self._url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.proxy = proxy
        self._client: httpx.AsyncClient | None = None

    def _client_kwargs(self) -> dict:
        kwargs: dict = {"timeout": 120}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(**self._client_kwargs())
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _convert_messages(self, system: str, messages: list[dict]) -> tuple[str, list[dict]]:
        """Convert OpenAI-style messages to Anthropic format.
        
        Anthropic requires system as a top-level param, not a message.
        Also requires alternating user/assistant roles.
        """
        converted = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system += "\n\n" + msg["content"]
                continue
            if role not in ("user", "assistant"):
                role = "user"
            if converted and converted[-1]["role"] == role:
                converted[-1]["content"] += "\n\n" + msg["content"]
            else:
                converted.append({"role": role, "content": msg["content"]})

        if not converted or converted[0]["role"] != "user":
            converted.insert(0, {"role": "user", "content": "Begin the discussion."})

        return system, converted

    async def completion(self, system: str, messages: list[dict]) -> str:
        system_text, converted = self._convert_messages(system, messages)
        client = await self._get_client()
        resp = await client.post(
            f"{self._url}/v1/messages",
            headers=self._headers(),
            json={
                "model": self.model,
                "system": system_text,
                "messages": converted,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    async def stream_completion(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None] | None],
    ) -> str:
        system_text, converted = self._convert_messages(system, messages)
        full_text = ""
        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self._url}/v1/messages",
            headers=self._headers(),
            json={
                "model": self.model,
                "system": system_text,
                "messages": converted,
                "max_tokens": 4096,
                "stream": True,
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "content_block_delta":
                    token = event.get("delta", {}).get("text", "")
                    if token:
                        full_text += token
                        result = on_token(token)
                        if result is not None:
                            await result
        return full_text

    async def json_completion(self, system: str, messages: list[dict]) -> str:
        system_text, converted = self._convert_messages(system, messages)
        system_text += "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        client = await self._get_client()
        resp = await client.post(
            f"{self._url}/v1/messages",
            headers=self._headers(),
            json={
                "model": self.model,
                "system": system_text,
                "messages": converted,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


register_provider("anthropic", AnthropicProvider)
