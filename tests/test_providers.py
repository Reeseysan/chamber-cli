import pytest

from chamber.providers.base import LLMProvider
from chamber.providers import registry, register_provider, get_provider, discover_providers


class FakeProvider(LLMProvider):
    async def stream_completion(self, system, messages, on_token):
        result = on_token("hello")
        if hasattr(result, "__await__"):
            await result
        return "hello"

    async def completion(self, system, messages):
        return "hello"

    async def json_completion(self, system, messages):
        return '{"result": "hello"}'


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()


def test_register_and_get_provider():
    register_provider("fake", lambda **kwargs: FakeProvider())
    provider = get_provider("fake")
    assert isinstance(provider, FakeProvider)


def test_get_unknown_provider_raises():
    with pytest.raises(KeyError, match="Unknown provider"):
        get_provider("nonexistent_provider_xyz")


def test_registry_is_a_dict():
    assert isinstance(registry, dict)


async def test_fake_provider_completion():
    p = FakeProvider()
    result = await p.completion("system", [{"role": "user", "content": "hi"}])
    assert result == "hello"


async def test_fake_provider_stream():
    p = FakeProvider()
    tokens = []
    result = await p.stream_completion("system", [{"role": "user", "content": "hi"}], lambda t: tokens.append(t))
    assert result == "hello"
    assert tokens == ["hello"]
