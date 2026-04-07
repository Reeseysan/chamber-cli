from __future__ import annotations

import os

from chamber.providers.base import OpenAICompatibleProvider
from chamber.providers import register_provider


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI API provider (api.openai.com)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        proxy: str | None = None,
    ):
        super().__init__()
        self.api_key = api_key or os.environ.get("CHAMBER_OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set CHAMBER_OPENAI_API_KEY or pass --provider ollama for local mode."
            )
        self.model = model or "gpt-4o"
        self._url = (base_url or "https://api.openai.com").rstrip("/")
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
        }

    def _json_completion_extra_body(self) -> dict:
        return {"response_format": {"type": "json_object"}}


register_provider("openai", OpenAIProvider)
