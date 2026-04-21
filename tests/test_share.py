from __future__ import annotations

import httpx
import pytest
import respx
from click.testing import CliRunner

from chamber.models import Message, Persona, Session
from chamber.share import build_payload, share_command, share_session


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return tmp_path


def _make_session() -> Session:
    personas = [
        Persona(name="Ada", role="Engineer", expertise="CS", avatar_emoji="💻"),
        Persona(name="Bo", role="Designer", expertise="UX", avatar_emoji="🎨"),
    ]
    s = Session(topic="shipping v0.5", personas=personas)
    s.current_round = 2
    s.messages.append(Message(agent_name="Ada", role="expert", content="ship it", round_number=1))
    s.messages.append(Message(agent_name="Bo", role="expert", content="polish first", round_number=1))
    s.messages.append(Message(agent_name="moderator", role="moderator", content="summary", round_number=1))
    return s


def test_build_payload_shape():
    session = _make_session()
    payload = build_payload(session)

    assert payload["session_id"] == session.id
    assert payload["topic"] == "shipping v0.5"
    assert payload["current_round"] == 2
    assert "cli_version" in payload
    assert len(payload["personas"]) == 2
    assert payload["personas"][0] == {
        "name": "Ada", "role": "Engineer", "expertise": "CS", "avatar_emoji": "💻",
    }
    assert len(payload["messages"]) == 3
    assert payload["messages"][0]["agent_name"] == "Ada"
    assert payload["messages"][0]["round_number"] == 1
    assert "timestamp" in payload["messages"][0]


@respx.mock
def test_share_session_success():
    url = "https://api.getchamber.ai/api/v1/share"
    share_url = "https://getchamber.ai/share/xyz123"
    route = respx.post(url).mock(return_value=httpx.Response(200, json={"url": share_url}))

    code = share_session(_make_session(), url)

    assert code == 0
    assert route.called
    sent_body = route.calls[0].request.content
    assert b"shipping v0.5" in sent_body


@respx.mock
def test_share_session_connection_error():
    url = "https://api.getchamber.ai/api/v1/share"
    respx.post(url).mock(side_effect=httpx.ConnectError("refused"))

    code = share_session(_make_session(), url)
    assert code == 1


@respx.mock
def test_share_session_http_error():
    url = "https://api.getchamber.ai/api/v1/share"
    respx.post(url).mock(return_value=httpx.Response(500, text="server down"))

    code = share_session(_make_session(), url)
    assert code == 1


@respx.mock
def test_share_session_missing_url_in_response():
    url = "https://api.getchamber.ai/api/v1/share"
    respx.post(url).mock(return_value=httpx.Response(200, json={"ok": True}))

    code = share_session(_make_session(), url)
    assert code == 1


@respx.mock
def test_share_command_end_to_end(tmp_home):
    # Seed store with a session, then run `chamber share`.
    from chamber.store import save_session
    session = _make_session()
    save_session(session)

    share_url = "https://getchamber.ai/share/abc"
    respx.post("https://api.getchamber.ai/api/v1/share").mock(
        return_value=httpx.Response(200, json={"url": share_url})
    )

    result = CliRunner().invoke(share_command, [])
    assert result.exit_code == 0
    assert share_url in result.output
    assert "Session published" in result.output


def test_share_command_errors_with_no_sessions(tmp_home):
    result = CliRunner().invoke(share_command, [])
    assert result.exit_code == 1
    assert "No local sessions" in result.output


def test_share_command_errors_with_unknown_session_id(tmp_home):
    result = CliRunner().invoke(share_command, ["--session-id", "nope"])
    assert result.exit_code == 1
    assert "nope" in result.output


@respx.mock
def test_share_command_uses_env_override(tmp_home, monkeypatch):
    from chamber.store import save_session
    save_session(_make_session())

    monkeypatch.setenv("CHAMBER_CLOUD_URL", "http://localhost:8000/api/v1/share")
    route = respx.post("http://localhost:8000/api/v1/share").mock(
        return_value=httpx.Response(200, json={"url": "http://localhost:8000/share/abc"})
    )

    result = CliRunner().invoke(share_command, [])
    assert result.exit_code == 0
    assert route.called
