import json
import pytest
import httpx
import respx

from tests.conftest import (
    LMSTUDIO_BASE,
    make_chat_completion_chunk,
    make_chat_completion_response,
    build_sse_stream,
)
from chamber.providers.lmstudio import LMStudioProvider


@respx.mock
async def test_lmstudio_check_available():
    respx.get(LMSTUDIO_BASE + "/v1/models").mock(return_value=httpx.Response(200, json={"data": []}))
    provider = LMStudioProvider()
    await provider.check_available()


@respx.mock
async def test_lmstudio_check_unavailable():
    respx.get(LMSTUDIO_BASE + "/v1/models").mock(side_effect=httpx.ConnectError("refused"))
    provider = LMStudioProvider()
    with pytest.raises(ConnectionError, match="LM Studio is not running"):
        await provider.check_available()


@respx.mock
async def test_lmstudio_completion():
    respx.get(LMSTUDIO_BASE + "/v1/models").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(LMSTUDIO_BASE + "/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=make_chat_completion_response("LM Studio says hi."))
    )
    provider = LMStudioProvider()
    result = await provider.completion("system", [{"role": "user", "content": "hi"}])
    assert result == "LM Studio says hi."


@respx.mock
async def test_lmstudio_stream_completion():
    respx.get(LMSTUDIO_BASE + "/v1/models").mock(return_value=httpx.Response(200, json={"data": []}))
    chunks = [
        make_chat_completion_chunk("Hello "),
        make_chat_completion_chunk("world."),
        make_chat_completion_chunk("", finish=True),
    ]
    sse_body = build_sse_stream(chunks)
    respx.post(LMSTUDIO_BASE + "/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})
    )
    provider = LMStudioProvider()
    tokens = []
    result = await provider.stream_completion(
        "system", [{"role": "user", "content": "hi"}], lambda t: tokens.append(t)
    )
    assert result == "Hello world."
    assert tokens == ["Hello ", "world."]


def test_lmstudio_default_config():
    p = LMStudioProvider()
    assert p.base_url == "http://localhost:1234"
    assert p.model == "local-model"


def test_lmstudio_custom_config():
    p = LMStudioProvider(base_url="http://myhost:5555", model="my-model")
    assert p.base_url == "http://myhost:5555"
    assert p.model == "my-model"
