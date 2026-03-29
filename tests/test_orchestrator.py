import json
import pytest

from chamber.models import Persona, Session
from chamber.orchestrator import Orchestrator
from chamber.providers.base import LLMProvider


class ScriptedProvider(LLMProvider):
    """Provider that returns scripted responses in order."""

    def __init__(self, responses: list[str], json_responses: list[str] | None = None):
        self._responses = list(responses)
        self._json_responses = list(json_responses or [])
        self._call_count = 0
        self._json_call_count = 0

    async def stream_completion(self, system, messages, on_token):
        text = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        for word in text.split():
            token = word + " "
            result = on_token(token)
            if result is not None:
                await result
        return text

    async def completion(self, system, messages):
        text = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        return text

    async def json_completion(self, system, messages):
        text = self._json_responses[self._json_call_count % len(self._json_responses)]
        self._json_call_count += 1
        return text


def make_session():
    personas = [
        Persona(name="Alice", role="Lawyer", expertise="Law", avatar_emoji="⚖️",
                system_prompt="You are Alice."),
        Persona(name="Bob", role="Engineer", expertise="Tech", avatar_emoji="🔧",
                system_prompt="You are Bob."),
    ]
    return Session(topic="Test topic", personas=personas, status="idle")


async def test_orchestrator_runs_to_completion():
    """Orchestrator should run all rounds and produce messages."""
    no_consensus = json.dumps({
        "reached": False, "summary": "No consensus.", "key_points": [], "dissenting_views": [],
    })
    final_consensus = json.dumps({
        "reached": True, "summary": "Agreed.", "key_points": ["yes"], "dissenting_views": [],
    })

    provider = ScriptedProvider(
        responses=["I think X.", "I think Y.", "Summary of round."],
        json_responses=[no_consensus, no_consensus, final_consensus],
    )
    session = make_session()
    tokens_received = []

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=3,
        on_token=lambda name, token: tokens_received.append((name, token)),
        on_round_start=lambda r: None,
        on_agent_start=lambda name: None,
        on_agent_done=lambda name, text: None,
        on_moderator=lambda text: None,
        on_consensus=lambda result: None,
    )

    await orchestrator.run()
    assert session.status == "ended"
    assert len(session.messages) > 0
    assert len(tokens_received) > 0


async def test_orchestrator_stops_on_consensus():
    """Orchestrator should stop early when consensus is reached."""
    consensus = json.dumps({
        "reached": True, "summary": "All agree.", "key_points": ["done"], "dissenting_views": [],
    })

    provider = ScriptedProvider(
        responses=["Point A.", "Point B.", "Round summary."],
        json_responses=[consensus],
    )
    session = make_session()
    rounds_started = []

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=5,
        on_token=lambda name, token: None,
        on_round_start=lambda r: rounds_started.append(r),
        on_agent_start=lambda name: None,
        on_agent_done=lambda name, text: None,
        on_moderator=lambda text: None,
        on_consensus=lambda result: None,
    )

    await orchestrator.run()
    assert len(rounds_started) == 1  # Stopped after first round


async def test_orchestrator_respects_max_rounds():
    no_consensus = json.dumps({
        "reached": False, "summary": "Nope.", "key_points": [], "dissenting_views": [],
    })

    provider = ScriptedProvider(
        responses=["Argument.", "Counter.", "Summary."],
        json_responses=[no_consensus, no_consensus],
    )
    session = make_session()
    rounds_started = []

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=2,
        on_token=lambda name, token: None,
        on_round_start=lambda r: rounds_started.append(r),
        on_agent_start=lambda name: None,
        on_agent_done=lambda name, text: None,
        on_moderator=lambda text: None,
        on_consensus=lambda result: None,
    )

    await orchestrator.run()
    assert len(rounds_started) == 2
    assert session.status == "ended"


async def test_orchestrator_handles_user_follow_up():
    no_consensus = json.dumps({
        "reached": False, "summary": "Nope.", "key_points": [], "dissenting_views": [],
    })
    consensus = json.dumps({
        "reached": True, "summary": "Done.", "key_points": ["yes"], "dissenting_views": [],
    })

    provider = ScriptedProvider(
        responses=["Point.", "Counter.", "Summary."],
        json_responses=[no_consensus, consensus],
    )
    session = make_session()

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=3,
        on_token=lambda name, token: None,
        on_round_start=lambda r: None,
        on_agent_start=lambda name: None,
        on_agent_done=lambda name, text: None,
        on_moderator=lambda text: None,
        on_consensus=lambda result: None,
    )

    orchestrator.inject_user_message("What about privacy?")
    await orchestrator.run()

    user_msgs = [m for m in session.messages if m.role == "user"]
    assert len(user_msgs) == 1
    assert "privacy" in user_msgs[0].content


async def test_orchestrator_with_document_context():
    """Orchestrator should pass document context to experts and moderator."""
    consensus = json.dumps({
        "reached": True, "summary": "Done.", "key_points": ["yes"], "dissenting_views": [],
    })

    provider = ScriptedProvider(
        responses=["Point.", "Counter.", "Summary."],
        json_responses=[consensus],
    )
    session = make_session()
    session.document_context = "[DOCUMENT: test.pdf]\n\nSome content."

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=1,
        depth="deep",
        on_token=lambda name, token: None,
    )

    await orchestrator.run()
    assert session.status == "ended"
    assert len(session.messages) > 0
