import json
import os
import tempfile
import pytest

from chamber.models import Persona
from chamber.persona import (
    generate_personas_from_roles,
    load_personas_from_file,
    build_system_prompt,
)
from chamber.providers.base import LLMProvider


class MockProvider(LLMProvider):
    def __init__(self, response: str):
        self._response = response

    async def stream_completion(self, system, messages, on_token):
        return self._response

    async def completion(self, system, messages):
        return self._response

    async def json_completion(self, system, messages):
        return self._response


MOCK_SEEDED_JSON = json.dumps([
    {
        "name": "Elena Voss",
        "role": "Maritime Lawyer",
        "expertise": "International shipping disputes",
        "avatar_emoji": "⚓",
    },
    {
        "name": "Marcus Webb",
        "role": "Tax Specialist",
        "expertise": "Offshore tax structures",
        "avatar_emoji": "💰",
    },
])


async def test_generate_from_roles():
    provider = MockProvider(MOCK_SEEDED_JSON)
    personas = await generate_personas_from_roles(
        roles=["Maritime Lawyer", "Tax Specialist"],
        topic="offshore claim",
        provider=provider,
    )
    assert len(personas) == 2
    assert all(isinstance(p, Persona) for p in personas)


async def test_generate_from_roles_includes_role_in_prompt():
    last_messages = []

    class CapturingProvider(LLMProvider):
        async def stream_completion(self, system, messages, on_token):
            return ""
        async def completion(self, system, messages):
            return ""
        async def json_completion(self, system, messages):
            last_messages.append(messages)
            return MOCK_SEEDED_JSON

    provider = CapturingProvider()
    await generate_personas_from_roles(
        roles=["Maritime Lawyer", "Tax Specialist"],
        topic="test",
        provider=provider,
    )
    prompt_text = last_messages[0][0]["content"]
    assert "Maritime Lawyer" in prompt_text
    assert "Tax Specialist" in prompt_text


def test_load_personas_from_file():
    panel = [
        {"role": "Lawyer", "expertise": "Contract law"},
        {"name": "Bob", "role": "Engineer", "expertise": "Systems", "avatar_emoji": "🔧"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(panel, f)
        f.flush()
        personas = load_personas_from_file(f.name)
    os.unlink(f.name)
    assert len(personas) == 2
    assert personas[0].role == "Lawyer"
    assert personas[0].name
    assert personas[0].system_prompt
    assert personas[1].name == "Bob"
    assert personas[1].avatar_emoji == "🔧"


def test_load_personas_from_file_missing_role():
    panel = [{"name": "Alice"}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(panel, f)
        f.flush()
        with pytest.raises(ValueError, match="role"):
            load_personas_from_file(f.name)
    os.unlink(f.name)


def test_load_personas_from_file_not_array():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"role": "Lawyer"}, f)
        f.flush()
        with pytest.raises(ValueError, match="array"):
            load_personas_from_file(f.name)
    os.unlink(f.name)


def test_build_system_prompt_with_word_limit():
    prompt = build_system_prompt("Alice", "Lawyer", "Contract law", word_limit=500)
    assert "500 words" in prompt
    assert "Alice" in prompt


def test_build_system_prompt_default_word_limit():
    prompt = build_system_prompt("Alice", "Lawyer", "Contract law")
    assert "200 words" in prompt
