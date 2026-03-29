import pytest

from chamber.models import Session, Persona, Message, ConsensusResult
from chamber.export import export_markdown, export_encrypted, decrypt_export


def make_session_with_messages():
    personas = [
        Persona(name="Alice", role="Lawyer", expertise="Law", avatar_emoji="⚖️", system_prompt=""),
        Persona(name="Bob", role="Engineer", expertise="Tech", avatar_emoji="🔧", system_prompt=""),
    ]
    messages = [
        Message(agent_name="Alice", role="expert", content="I think X.", round_number=1),
        Message(agent_name="Bob", role="expert", content="I think Y.", round_number=1),
        Message(agent_name="Moderator", role="moderator", content="Summary of round 1.", round_number=1),
        Message(agent_name="User", role="user", content="What about Z?", round_number=1),
        Message(agent_name="Alice", role="expert", content="Good point about Z.", round_number=2),
        Message(agent_name="Bob", role="expert", content="Z changes things.", round_number=2),
        Message(agent_name="Moderator", role="moderator", content="Consensus reached.", round_number=2),
    ]
    return Session(topic="Test topic", personas=personas, messages=messages, current_round=2)


def test_export_markdown_contains_topic():
    session = make_session_with_messages()
    md = export_markdown(session)
    assert "Test topic" in md


def test_export_markdown_contains_all_agents():
    session = make_session_with_messages()
    md = export_markdown(session)
    assert "Alice" in md
    assert "Bob" in md
    assert "Moderator" in md


def test_export_markdown_contains_round_headers():
    session = make_session_with_messages()
    md = export_markdown(session)
    assert "Round 1" in md
    assert "Round 2" in md


def test_export_markdown_contains_user_message():
    session = make_session_with_messages()
    md = export_markdown(session)
    assert "What about Z?" in md


def test_export_markdown_empty_session():
    session = Session(topic="Empty")
    md = export_markdown(session)
    assert "Empty" in md


def test_encrypted_export_round_trip():
    session = make_session_with_messages()
    md = export_markdown(session)
    passphrase = "test-passphrase-123"
    encrypted = export_encrypted(md, passphrase)
    assert encrypted != md.encode()
    decrypted = decrypt_export(encrypted, passphrase)
    assert decrypted == md


def test_encrypted_export_wrong_passphrase():
    md = "Some content"
    encrypted = export_encrypted(md, "correct-pass")
    with pytest.raises(Exception):
        decrypt_export(encrypted, "wrong-pass")
