from __future__ import annotations

import os

from chamber.providers.base import OpenAICompatibleProvider
from chamber.providers import register_provider


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter API provider (openrouter.ai). OpenAI-compatible with different auth."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        proxy: str | None = None,
    ):
        super().__init__()
        self.api_key = api_key or os.environ.get("CHAMBER_OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set CHAMBER_OPENROUTER_API_KEY or pass --provider ollama for local mode."
            )
        self.model = model or "meta-llama/llama-3.1-8b-instruct"
        self._url = (base_url or "https://openrouter.ai/api").rstrip("/")
        self.proxy = proxy

    def _base_url(self) -> str:
        return self._url

    def _client_kwargs(self) -> dict:
        kwargs: dict = {"timeout": 120}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/reeseysan/chamber-cli",
            "X-Title": "Chamber CLI",
        }


register_provider("openrouter", OpenRouterProvider)
