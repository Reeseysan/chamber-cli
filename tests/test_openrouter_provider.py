"""Tests for OpenRouter provider."""
from __future__ import annotations

import os
import json
from unittest.mock import patch

import pytest
import httpx
import respx

from chamber.providers.base import LLMProvider


@pytest.fixture
def openrouter_provider():
    with patch.dict(os.environ, {"CHAMBER_OPENROUTER_API_KEY": "test-key-123"}, clear=False):
        from chamber.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(api_key="test-key-123")


def test_openrouter_requires_api_key():
    with patch.dict(os.environ, {}, clear=True):
        from chamber.providers.openrouter import OpenRouterProvider
        with pytest.raises(ValueError, match="API key required"):
            OpenRouterProvider()


def test_openrouter_implements_interface(openrouter_provider):
    assert isinstance(openrouter_provider, LLMProvider)


def test_openrouter_default_model(openrouter_provider):
    assert "llama" in openrouter_provider.model.lower()


def test_openrouter_headers(openrouter_provider):
    headers = openrouter_provider._headers()
    assert headers["Authorization"] == "Bearer test-key-123"
    assert "HTTP-Referer" in headers
    assert "X-Title" in headers


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_completion(openrouter_provider):
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": "Hello from OpenRouter"}}]
        })
    )
    result = await openrouter_provider.completion("System", [{"role": "user", "content": "Hi"}])
    assert result == "Hello from OpenRouter"


def test_openrouter_proxy():
    with patch.dict(os.environ, {"CHAMBER_OPENROUTER_API_KEY": "test-key"}, clear=False):
        from chamber.providers.openrouter import OpenRouterProvider
        p = OpenRouterProvider(api_key="test-key", proxy="socks5://localhost:9050")
        kwargs = p._client_kwargs()
        assert kwargs["proxy"] == "socks5://localhost:9050"
