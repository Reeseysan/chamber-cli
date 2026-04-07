"""Tests for remote OpenAI provider."""
from __future__ import annotations

import os
import json
from unittest.mock import patch, AsyncMock

import pytest
import httpx
import respx

from chamber.providers.base import LLMProvider


@pytest.fixture
def openai_provider():
    with patch.dict(os.environ, {"CHAMBER_OPENAI_API_KEY": "test-key-123"}, clear=False):
        from chamber.providers.openai import OpenAIProvider
        return OpenAIProvider(api_key="test-key-123", model="gpt-4o")


def test_openai_requires_api_key():
    with patch.dict(os.environ, {}, clear=True):
        from chamber.providers.openai import OpenAIProvider
        with pytest.raises(ValueError, match="API key required"):
            OpenAIProvider()


def test_openai_implements_interface(openai_provider):
    assert isinstance(openai_provider, LLMProvider)
    assert openai_provider.model == "gpt-4o"


@pytest.mark.asyncio
@respx.mock
async def test_openai_completion(openai_provider):
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": "Hello from GPT"}}]
        })
    )
    result = await openai_provider.completion("You are helpful.", [{"role": "user", "content": "Hi"}])
    assert result == "Hello from GPT"


@pytest.mark.asyncio
@respx.mock
async def test_openai_json_completion(openai_provider):
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": '{"key": "value"}'}}]
        })
    )
    result = await openai_provider.json_completion("Return JSON.", [{"role": "user", "content": "data"}])
    parsed = json.loads(result)
    assert parsed["key"] == "value"


def test_openai_proxy_support():
    with patch.dict(os.environ, {"CHAMBER_OPENAI_API_KEY": "test-key"}, clear=False):
        from chamber.providers.openai import OpenAIProvider
        p = OpenAIProvider(api_key="test-key", proxy="socks5://localhost:9050")
        assert p.proxy == "socks5://localhost:9050"
        kwargs = p._client_kwargs()
        assert kwargs["proxy"] == "socks5://localhost:9050"
