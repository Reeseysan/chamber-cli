import json
import pytest

from chamber.models import Message, ConsensusResult
from chamber.moderator import ModeratorAgent
from chamber.providers.base import LLMProvider


class MockModProvider(LLMProvider):
    def __init__(self, completion_text: str = "", json_text: str = "{}"):
        self._completion = completion_text
        self._json = json_text
        self.last_system = None

    async def stream_completion(self, system, messages, on_token):
        return self._completion

    async def completion(self, system, messages):
        self.last_system = system
        return self._completion

    async def json_completion(self, system, messages):
        self.last_system = system
        return self._json


def sample_history():
    return [
        Message(agent_name="Alice", role="expert", content="I think X.", round_number=1),
        Message(agent_name="Bob", role="expert", content="I disagree, Y.", round_number=1),
    ]


async def test_consensus_brief_prompt():
    consensus_json = json.dumps({
        "reached": True, "summary": "Brief.", "key_points": ["X"], "dissenting_views": [],
    })
    provider = MockModProvider(json_text=consensus_json)
    mod = ModeratorAgent(provider=provider)
    await mod.check_consensus(sample_history(), round_number=1, max_rounds=3, depth="brief")
    assert "concise" in provider.last_system.lower() or "brief" in provider.last_system.lower()


async def test_consensus_deep_prompt():
    consensus_json = json.dumps({
        "reached": True, "summary": "Deep.", "key_points": ["X"], "dissenting_views": [],
    })
    provider = MockModProvider(json_text=consensus_json)
    mod = ModeratorAgent(provider=provider)
    await mod.check_consensus(sample_history(), round_number=1, max_rounds=3, depth="deep")
    assert "RISK FACTORS" in provider.last_system or "NEXT STEPS" in provider.last_system


async def test_consensus_standard_prompt():
    consensus_json = json.dumps({
        "reached": True, "summary": "Standard.", "key_points": ["X"], "dissenting_views": [],
    })
    provider = MockModProvider(json_text=consensus_json)
    mod = ModeratorAgent(provider=provider)
    await mod.check_consensus(sample_history(), round_number=1, max_rounds=3, depth="standard")
    assert "VERDICT" in provider.last_system


async def test_summary_uses_word_limit():
    provider = MockModProvider(completion_text="Summary here.")
    mod = ModeratorAgent(provider=provider)
    await mod.summarize_round(sample_history(), round_number=1, summary_limit=300)
    assert "300" in provider.last_system


async def test_moderator_document_context():
    provider = MockModProvider(completion_text="Summary.")
    mod = ModeratorAgent(provider=provider)
    await mod.summarize_round(
        sample_history(), round_number=1, summary_limit=200,
        document_context="[DOCUMENT: test.pdf]\n\nContent here",
    )
    assert "test.pdf" in provider.last_system or "Content here" in provider.last_system
