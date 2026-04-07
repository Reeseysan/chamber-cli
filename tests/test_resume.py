"""Tests for session resume module."""
from __future__ import annotations

import pytest

from chamber.resume import parse_exported_markdown, _parse_panel, _is_encrypted, EXPORT_HEADER
from chamber.export import export_markdown
from chamber.models import Session, Persona, Message


def _make_session():
    personas = [
        Persona(name="Alice", role="Engineer", expertise="Backend systems", avatar_emoji="💻", system_prompt="..."),
        Persona(name="Bob", role="Designer", expertise="UX research", avatar_emoji="🎨", system_prompt="..."),
    ]
    messages = [
        Message(agent_name="Alice", role="expert", content="I think we should use Go.", round_number=1, session_id="test"),
        Message(agent_name="Bob", role="expert", content="React would be better.", round_number=1, session_id="test"),
        Message(agent_name="Moderator", role="moderator", content="Both have merits.", round_number=1, session_id="test"),
    ]
    return Session(id="test", topic="Best tech stack", personas=personas, messages=messages, current_round=1)


def test_roundtrip_export_resume():
    """Export a session, then resume it — data should survive."""
    original = _make_session()
    md = export_markdown(original)
    resumed = parse_exported_markdown(md)

    assert resumed.topic == "Best tech stack"
    assert len(resumed.personas) == 2
    assert resumed.personas[0].name == "Alice"
    assert resumed.personas[1].name == "Bob"
    assert len(resumed.messages) == 3
    assert resumed.messages[0].agent_name == "Alice"
    assert resumed.messages[0].content == "I think we should use Go."
    assert resumed.messages[2].role == "moderator"


def test_parse_panel():
    text = (
        "- **Alice** — Engineer (Backend systems)\n"
        "- **Bob** — Designer (UX research)\n"
    )
    personas = _parse_panel(text)
    assert len(personas) == 2
    assert personas[0].name == "Alice"
    assert personas[0].role == "Engineer"
    assert personas[1].expertise == "UX research"


def test_parse_topic():
    md = "# Chamber Discussion: My cool topic\n\n## Panel\n- **A** — B (C)\n"
    session = parse_exported_markdown(md)
    assert session.topic == "My cool topic"


def test_parse_handles_export_header():
    md = f"{EXPORT_HEADER}\n# Chamber Discussion: Topic\n\n## Panel\n- **A** — B (C)\n"
    session = parse_exported_markdown(md)
    assert session.topic == "Topic"


def test_is_encrypted_plaintext():
    assert _is_encrypted(b"# Chamber Discussion") is False


def test_is_encrypted_binary():
    assert _is_encrypted(b"\x89\x50\x4e\x47\x0d\x0a") is True


def test_parse_multiple_rounds():
    md = """# Chamber Discussion: Topic

## Panel
- **Alice** — Engineer (Code)

## Round 1

### [Alice]

Round 1 content.

## Round 2

### [Alice]

Round 2 content.
"""
    session = parse_exported_markdown(md)
    assert len(session.messages) == 2
    assert session.messages[0].round_number == 1
    assert session.messages[1].round_number == 2


def test_parse_user_messages():
    md = """# Chamber Discussion: Topic

## Panel
- **Alice** — Engineer (Code)

## Round 1

### You

User follow-up question

### [Alice]

Expert response
"""
    session = parse_exported_markdown(md)
    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[0].agent_name == "User"
