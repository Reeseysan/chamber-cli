from __future__ import annotations

import httpx

from chamber.providers.base import OpenAICompatibleProvider
from chamber.providers import register_provider


class LMStudioProvider(OpenAICompatibleProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        super().__init__()
        self._url = (base_url or "http://localhost:1234").rstrip("/")
        self.model = model or "local-model"

    def _base_url(self) -> str:
        return self._url

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    async def check_available(self) -> None:
        """Check if LM Studio local server is reachable and detect loaded model."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self._url}/v1/models")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            if models and self.model == "local-model":
                self.model = models[0].get("id", "local-model")
        except (httpx.ConnectError, httpx.TimeoutException):
            raise ConnectionError(
                f"LM Studio is not running at {self._url}.\n"
                "Start the local server: LM Studio → Developer → Start Server"
            )


register_provider("lmstudio", LMStudioProvider)
