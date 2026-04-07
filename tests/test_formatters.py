"""Tests for formatters module."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from chamber.formatters import format_session_json
from chamber.models import Session, Persona, Message, ConsensusResult


def _make_session():
    personas = [
        Persona(name="Alice", role="Engineer", expertise="Backend systems", avatar_emoji="💻"),
        Persona(name="Bob", role="Designer", expertise="UX research", avatar_emoji="🎨"),
    ]
    messages = [
        Message(agent_name="Alice", role="expert", content="I think we should use Go.", round_number=1, session_id="test"),
        Message(agent_name="Bob", role="expert", content="React would be better.", round_number=1, session_id="test"),
        Message(agent_name="Moderator", role="moderator", content="Both have merits.", round_number=1, session_id="test"),
    ]
    return Session(id="test", topic="Best tech stack", personas=personas, messages=messages, current_round=1)


def test_format_session_json_structure():
    session = _make_session()
    result = format_session_json(session)
    data = json.loads(result)

    assert data["topic"] == "Best tech stack"
    assert len(data["experts"]) == 2
    assert data["experts"][0]["name"] == "Alice"
    assert data["experts"][1]["name"] == "Bob"
    assert len(data["rounds"]) == 1
    assert data["rounds"][0]["number"] == 1
    assert len(data["rounds"][0]["contributions"]) == 2
    assert data["rounds"][0]["moderator_summary"] == "Both have merits."
    assert data["consensus"] is None


def test_format_session_json_with_consensus():
    session = _make_session()
    consensus = ConsensusResult(
        reached=True,
        summary="Go is better for this use case.",
        key_points=["Performance", "Type safety"],
        dissenting_views=["React is more popular"],
    )
    result = format_session_json(session, consensus)
    data = json.loads(result)

    assert data["consensus"]["reached"] is True
    assert data["consensus"]["summary"] == "Go is better for this use case."
    assert len(data["consensus"]["key_points"]) == 2


def test_format_session_json_is_valid_json():
    session = _make_session()
    result = format_session_json(session)
    # Should not raise
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_format_session_json_multiple_rounds():
    session = _make_session()
    session.messages.append(
        Message(agent_name="Alice", role="expert", content="Round 2 thoughts", round_number=2, session_id="test")
    )
    result = format_session_json(session)
    data = json.loads(result)
    assert len(data["rounds"]) == 2
    assert data["rounds"][1]["number"] == 2
