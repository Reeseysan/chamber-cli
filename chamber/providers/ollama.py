from __future__ import annotations

import httpx

from chamber.providers.base import OpenAICompatibleProvider
from chamber.providers import register_provider


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        super().__init__()
        self._url = (base_url or "http://localhost:11434").rstrip("/")
        self.model = model or "llama3.1"

    def _base_url(self) -> str:
        return self._url

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _json_completion_extra_body(self) -> dict:
        return {"format": "json"}

    async def check_available(self) -> None:
        """Check if Ollama is reachable. Raises ConnectionError if not."""
        try:
            client = await self._get_client()
            await client.get(f"{self._url}/")
        except (httpx.ConnectError, httpx.TimeoutException):
            raise ConnectionError(
                f"Ollama is not running at {self._url}. "
                "Start it with: ollama serve"
            )


register_provider("ollama", OllamaProvider)
