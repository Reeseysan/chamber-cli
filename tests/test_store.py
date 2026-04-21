from __future__ import annotations

import time

import pytest

from chamber.models import Message, Persona, Session, SessionStatus
from chamber import store


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return tmp_path


def _make_session(topic: str = "test topic") -> Session:
    personas = [Persona(name="Ada", role="Engineer", expertise="CS", avatar_emoji="💻")]
    s = Session(topic=topic, personas=personas, status=SessionStatus.ENDED)
    s.messages.append(Message(agent_name="Ada", role="expert", content="hello", round_number=1))
    return s


def test_save_and_load_roundtrip(tmp_home):
    session = _make_session("roundtrip")
    path = store.save_session(session)
    assert path.exists()

    loaded = store.load_session(session.id)
    assert loaded.id == session.id
    assert loaded.topic == "roundtrip"
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content == "hello"


def test_load_missing_session_raises(tmp_home):
    with pytest.raises(FileNotFoundError):
        store.load_session("does-not-exist")


def test_latest_returns_none_when_empty(tmp_home):
    assert store.latest_session() is None


def test_latest_picks_most_recent(tmp_home):
    older = _make_session("older")
    store.save_session(older)
    time.sleep(0.01)  # ensure distinct mtimes
    newer = _make_session("newer")
    store.save_session(newer)

    latest = store.latest_session()
    assert latest is not None
    assert latest.topic == "newer"


def test_store_dir_is_under_home(tmp_home):
    assert store.store_dir() == tmp_home / ".chamber" / "sessions"
    assert store.store_dir().is_dir()
