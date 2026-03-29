import json
import pytest

from chamber.models import Persona
from chamber.persona import generate_personas, build_system_prompt, GENERATE_PROMPT
from chamber.providers.base import LLMProvider


class MockProvider(LLMProvider):
    def __init__(self, json_response: str):
        self._response = json_response

    async def stream_completion(self, system, messages, on_token):
        return self._response

    async def completion(self, system, messages):
        return self._response

    async def json_completion(self, system, messages):
        return self._response


MOCK_PERSONAS_JSON = json.dumps([
    {
        "name": "Alice Chen",
        "role": "Constitutional Lawyer",
        "expertise": "First Amendment case law and press freedom",
        "avatar_emoji": "⚖️",
    },
    {
        "name": "Bob Reeves",
        "role": "Investigative Journalist",
        "expertise": "Source protection and publication ethics",
        "avatar_emoji": "📰",
    },
    {
        "name": "Carol Diaz",
        "role": "National Security Analyst",
        "expertise": "Classification policy and prosecution risk",
        "avatar_emoji": "🔒",
    },
])


async def test_generate_personas_returns_correct_count():
    provider = MockProvider(MOCK_PERSONAS_JSON)
    personas = await generate_personas("Test topic", provider, count=3)
    assert len(personas) == 3


async def test_generate_personas_are_persona_objects():
    provider = MockProvider(MOCK_PERSONAS_JSON)
    personas = await generate_personas("Test topic", provider, count=3)
    for p in personas:
        assert isinstance(p, Persona)


async def test_generate_personas_have_system_prompts():
    provider = MockProvider(MOCK_PERSONAS_JSON)
    personas = await generate_personas("Test topic", provider, count=3)
    for p in personas:
        assert p.system_prompt
        assert p.name in p.system_prompt
        assert p.role in p.system_prompt


async def test_generate_personas_have_all_fields():
    provider = MockProvider(MOCK_PERSONAS_JSON)
    personas = await generate_personas("Test topic", provider, count=3)
    p = personas[0]
    assert p.name == "Alice Chen"
    assert p.role == "Constitutional Lawyer"
    assert p.expertise == "First Amendment case law and press freedom"
    assert p.avatar_emoji == "⚖️"


def test_build_system_prompt():
    prompt = build_system_prompt("Alice Chen", "Lawyer", "First Amendment law")
    assert "Alice Chen" in prompt
    assert "Lawyer" in prompt
    assert "concise" in prompt.lower() or "200 words" in prompt


async def test_generate_personas_strips_markdown_fences():
    fenced = "```json\n" + MOCK_PERSONAS_JSON + "\n```"
    provider = MockProvider(fenced)
    personas = await generate_personas("Test topic", provider, count=3)
    assert len(personas) == 3


def test_generate_prompt_template():
    assert "{count}" in GENERATE_PROMPT
    assert "{topic}" in GENERATE_PROMPT


async def test_generate_personas_retries_on_bad_json():
    """Should retry up to 3 times on invalid JSON."""
    call_count = 0

    class RetryProvider(LLMProvider):
        async def stream_completion(self, system, messages, on_token):
            return ""

        async def completion(self, system, messages):
            return ""

        async def json_completion(self, system, messages):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return "not valid json"
            return MOCK_PERSONAS_JSON

    provider = RetryProvider()
    personas = await generate_personas("Test topic", provider, count=3)
    assert len(personas) == 3
    assert call_count == 3


async def test_generate_personas_raises_after_3_failures():
    class AlwaysBadProvider(LLMProvider):
        async def stream_completion(self, system, messages, on_token):
            return ""

        async def completion(self, system, messages):
            return ""

        async def json_completion(self, system, messages):
            return "not json"

    provider = AlwaysBadProvider()
    with pytest.raises(RuntimeError, match="Failed to generate valid personas"):
        await generate_personas("Test topic", provider, count=3)


async def test_generate_personas_handles_dict_wrapper():
    """Some models wrap the array in a dict like {"experts": [...]}."""
    wrapped = json.dumps({"experts": json.loads(MOCK_PERSONAS_JSON)})
    provider = MockProvider(wrapped)
    personas = await generate_personas("Test topic", provider, count=3)
    assert len(personas) == 3
