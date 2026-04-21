from __future__ import annotations

from pathlib import Path

from chamber.models import Session


def store_dir() -> Path:
    """Local directory where completed sessions are cached for sharing/export.

    Lives under the user's home so data never leaves the machine until the
    user explicitly runs `chamber share`.
    """
    path = Path.home() / ".chamber" / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_session(session: Session) -> Path:
    """Persist a session as JSON. Overwrites if the same id already exists."""
    path = store_dir() / f"{session.id}.json"
    path.write_text(session.model_dump_json(indent=2))
    return path


def load_session(session_id: str) -> Session:
    """Load a session by id. Raises FileNotFoundError if missing."""
    path = store_dir() / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No session with id {session_id!r} in {store_dir()}")
    return Session.model_validate_json(path.read_text())


def latest_session() -> Session | None:
    """Return the most recently modified stored session, or None if empty."""
    files = sorted(store_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return Session.model_validate_json(files[0].read_text())
