import json
import pytest
import httpx
import respx

from tests.conftest import (
    OLLAMA_BASE,
    make_chat_completion_chunk,
    make_chat_completion_response,
    build_sse_stream,
)
from chamber.providers.ollama import OllamaProvider


@respx.mock
async def test_ollama_check_available():
    respx.get(OLLAMA_BASE + "/").mock(return_value=httpx.Response(200, text="Ollama is running"))
    provider = OllamaProvider()
    await provider.check_available()  # Should not raise


@respx.mock
async def test_ollama_check_unavailable():
    respx.get(OLLAMA_BASE + "/").mock(side_effect=httpx.ConnectError("refused"))
    provider = OllamaProvider()
    with pytest.raises(ConnectionError, match="Ollama is not running"):
        await provider.check_available()


@respx.mock
async def test_ollama_completion():
    respx.get(OLLAMA_BASE + "/").mock(return_value=httpx.Response(200))
    respx.post(OLLAMA_BASE + "/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=make_chat_completion_response("The answer is 42."))
    )
    provider = OllamaProvider()
    result = await provider.completion("You are helpful.", [{"role": "user", "content": "What is the answer?"}])
    assert result == "The answer is 42."


@respx.mock
async def test_ollama_stream_completion():
    respx.get(OLLAMA_BASE + "/").mock(return_value=httpx.Response(200))
    chunks = [
        make_chat_completion_chunk("The "),
        make_chat_completion_chunk("answer."),
        make_chat_completion_chunk("", finish=True),
    ]
    sse_body = build_sse_stream(chunks)
    respx.post(OLLAMA_BASE + "/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_body, headers={"content-type": "text/event-stream"})
    )
    provider = OllamaProvider()
    tokens = []
    result = await provider.stream_completion(
        "system", [{"role": "user", "content": "hi"}], lambda t: tokens.append(t)
    )
    assert result == "The answer."
    assert tokens == ["The ", "answer."]


@respx.mock
async def test_ollama_json_completion():
    respx.get(OLLAMA_BASE + "/").mock(return_value=httpx.Response(200))
    respx.post(OLLAMA_BASE + "/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=make_chat_completion_response('{"name": "Alice"}'))
    )
    provider = OllamaProvider()
    result = await provider.json_completion("Return JSON.", [{"role": "user", "content": "name?"}])
    assert json.loads(result) == {"name": "Alice"}


def test_ollama_default_config():
    p = OllamaProvider()
    assert p.base_url == "http://localhost:11434"
    assert p.model == "llama3.1"


def test_ollama_custom_config():
    p = OllamaProvider(base_url="http://myhost:9999", model="mistral")
    assert p.base_url == "http://myhost:9999"
    assert p.model == "mistral"
