"""Tests for Anthropic provider."""
from __future__ import annotations

import os
import json
from unittest.mock import patch

import pytest
import httpx
import respx

from chamber.providers.base import LLMProvider


@pytest.fixture
def anthropic_provider():
    with patch.dict(os.environ, {"CHAMBER_ANTHROPIC_API_KEY": "test-key-123"}, clear=False):
        from chamber.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key="test-key-123", model="claude-sonnet-4-20250514")


def test_anthropic_requires_api_key():
    with patch.dict(os.environ, {}, clear=True):
        from chamber.providers.anthropic import AnthropicProvider
        with pytest.raises(ValueError, match="API key required"):
            AnthropicProvider()


def test_anthropic_implements_interface(anthropic_provider):
    assert isinstance(anthropic_provider, LLMProvider)
    assert anthropic_provider.model == "claude-sonnet-4-20250514"


def test_anthropic_message_conversion(anthropic_provider):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "How are you?"},
    ]
    system, converted = anthropic_provider._convert_messages("System prompt", messages)
    assert system == "System prompt"
    assert len(converted) == 3
    assert converted[0]["role"] == "user"
    assert converted[1]["role"] == "assistant"
    assert converted[2]["role"] == "user"


def test_anthropic_merges_consecutive_roles(anthropic_provider):
    messages = [
        {"role": "user", "content": "First"},
        {"role": "user", "content": "Second"},
    ]
    system, converted = anthropic_provider._convert_messages("System", messages)
    assert len(converted) == 1
    assert "First" in converted[0]["content"]
    assert "Second" in converted[0]["content"]


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_completion(anthropic_provider):
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={
            "content": [{"type": "text", "text": "Hello from Claude"}]
        })
    )
    result = await anthropic_provider.completion("You are helpful.", [{"role": "user", "content": "Hi"}])
    assert result == "Hello from Claude"


def test_anthropic_headers(anthropic_provider):
    headers = anthropic_provider._headers()
    assert headers["x-api-key"] == "test-key-123"
    assert "anthropic-version" in headers
