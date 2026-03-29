from __future__ import annotations

import json
from typing import Callable, Awaitable

import httpx

from chamber.providers.base import LLMProvider
from chamber.providers import register_provider


class LMStudioProvider(LLMProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or "http://localhost:1234").rstrip("/")
        self.model = model or "local-model"

    async def check_available(self) -> None:
        """Check if LM Studio local server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.get(f"{self.base_url}/v1/models")
        except (httpx.ConnectError, httpx.TimeoutException):
            raise ConnectionError(
                f"LM Studio is not running at {self.base_url}. "
                "Start the local server in LM Studio."
            )

    async def completion(self, system: str, messages: list[dict]) -> str:
        await self.check_available()
        full_messages = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
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
        await self.check_available()
        full_messages = [{"role": "system", "content": system}] + messages
        full_text = ""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json={"model": self.model, "messages": full_messages, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        full_text += token
                        result = on_token(token)
                        if result is not None:
                            await result
        return full_text

    async def json_completion(self, system: str, messages: list[dict]) -> str:
        await self.check_available()
        full_messages = [{"role": "system", "content": system}] + messages
        full_messages[0]["content"] += "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={"model": self.model, "messages": full_messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


register_provider("lmstudio", LMStudioProvider)
