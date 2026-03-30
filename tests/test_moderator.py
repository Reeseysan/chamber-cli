import json
import pytest

from chamber.models import Message, ConsensusResult
from chamber.moderator import ModeratorAgent
from chamber.providers.base import LLMProvider


class MockModProvider(LLMProvider):
    def __init__(self, completion_text: str = "", json_text: str = "{}"):
        self._completion = completion_text
        self._json = json_text

    async def stream_completion(self, system, messages, on_token):
        return self._completion

    async def completion(self, system, messages):
        return self._completion

    async def json_completion(self, system, messages):
        return self._json


def sample_history():
    return [
        Message(agent_name="Alice", role="expert", content="I think X.", round_number=1),
        Message(agent_name="Bob", role="expert", content="I disagree, Y.", round_number=1),
        Message(agent_name="Carol", role="expert", content="Compromise: Z.", round_number=1),
    ]


async def test_summarize_round_returns_text():
    provider = MockModProvider(completion_text="Alice argued X, Bob countered with Y.")
    mod = ModeratorAgent(provider=provider)
    result = await mod.summarize_round(sample_history(), round_number=1)
    assert "Alice" in result or len(result) > 0


async def test_check_consensus_not_reached():
    consensus_json = json.dumps({
        "reached": False,
        "summary": "No agreement yet.",
        "key_points": ["X", "Y"],
        "dissenting_views": ["Z"],
    })
    provider = MockModProvider(json_text=consensus_json)
    mod = ModeratorAgent(provider=provider)
    result = await mod.check_consensus(sample_history(), round_number=1, max_rounds=3)
    assert isinstance(result, ConsensusResult)
    assert result.reached is False


async def test_check_consensus_reached():
    consensus_json = json.dumps({
        "reached": True,
        "summary": "Experts agree on Z.",
        "key_points": ["Z is best"],
        "dissenting_views": [],
    })
    provider = MockModProvider(json_text=consensus_json)
    mod = ModeratorAgent(provider=provider)
    result = await mod.check_consensus(sample_history(), round_number=2, max_rounds=3)
    assert result.reached is True
    assert "Z" in result.summary


async def test_check_consensus_handles_markdown_fences():
    fenced = "```json\n" + json.dumps({
        "reached": True, "summary": "OK", "key_points": [], "dissenting_views": [],
    }) + "\n```"
    provider = MockModProvider(json_text=fenced)
    mod = ModeratorAgent(provider=provider)
    result = await mod.check_consensus(sample_history(), round_number=1, max_rounds=3)
    assert result.reached is True


async def test_check_consensus_handles_invalid_json():
    provider = MockModProvider(json_text="not valid json at all")
    mod = ModeratorAgent(provider=provider)
    result = await mod.check_consensus(sample_history(), round_number=1, max_rounds=3)
    assert result.reached is False
    # When JSON parsing fails but model returned prose, use it as the summary
    assert result.summary == "not valid json at all"
