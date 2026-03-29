import pytest

from chamber.models import Persona, Message
from chamber.expert import ExpertAgent
from chamber.providers.base import LLMProvider


class RecordingProvider(LLMProvider):
    def __init__(self):
        self.last_system = None
        self.last_messages = None

    async def stream_completion(self, system, messages, on_token):
        self.last_system = system
        self.last_messages = messages
        text = "I think the answer is clear."
        result = on_token(text)
        if result is not None:
            await result
        return text

    async def completion(self, system, messages):
        self.last_system = system
        self.last_messages = messages
        return "I think the answer is clear."

    async def json_completion(self, system, messages):
        return '{}'


def make_persona():
    return Persona(
        name="Alice Chen",
        role="Lawyer",
        expertise="Constitutional law",
        avatar_emoji="⚖️",
        system_prompt="You are Alice Chen, a Lawyer. Constitutional law",
    )


async def test_expert_take_turn_returns_text():
    provider = RecordingProvider()
    expert = ExpertAgent(persona=make_persona(), provider=provider)
    tokens = []
    result = await expert.take_turn(
        history=[], round_number=1, on_token=lambda t: tokens.append(t)
    )
    assert result == "I think the answer is clear."
    assert len(tokens) == 1


async def test_expert_uses_persona_system_prompt():
    provider = RecordingProvider()
    expert = ExpertAgent(persona=make_persona(), provider=provider)
    await expert.take_turn(history=[], round_number=1, on_token=lambda t: None)
    assert "Alice Chen" in provider.last_system


async def test_expert_builds_messages_from_history():
    provider = RecordingProvider()
    expert = ExpertAgent(persona=make_persona(), provider=provider)
    history = [
        Message(agent_name="User", role="user", content="What about privacy?", round_number=1),
        Message(agent_name="Bob", role="expert", content="I think X.", round_number=1),
    ]
    await expert.take_turn(history=history, round_number=1, on_token=lambda t: None)
    msgs = provider.last_messages
    assert len(msgs) == 2
    # User message should be wrapped for injection protection
    assert "USER INPUT" in msgs[0]["content"]
    # Other expert's message should be attributed
    assert "[Bob]" in msgs[1]["content"]


async def test_expert_own_messages_are_assistant_role():
    provider = RecordingProvider()
    expert = ExpertAgent(persona=make_persona(), provider=provider)
    history = [
        Message(agent_name="Alice Chen", role="expert", content="My earlier point.", round_number=1),
        Message(agent_name="Bob", role="expert", content="I disagree.", round_number=1),
    ]
    await expert.take_turn(history=history, round_number=2, on_token=lambda t: None)
    msgs = provider.last_messages
    assert msgs[0]["role"] == "assistant"
    assert msgs[1]["role"] == "user"


async def test_expert_empty_history_gets_opening_prompt():
    provider = RecordingProvider()
    expert = ExpertAgent(persona=make_persona(), provider=provider)
    await expert.take_turn(history=[], round_number=1, on_token=lambda t: None)
    msgs = provider.last_messages
    assert len(msgs) == 1
    assert "opening thoughts" in msgs[0]["content"].lower() or "starting" in msgs[0]["content"].lower()
