from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class LLMProvider(ABC):
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
