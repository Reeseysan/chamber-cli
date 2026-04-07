from __future__ import annotations

from chamber.models import Session, SessionStatus, Persona


def create_session(topic: str, personas: list[Persona]) -> Session:
    """Create a new in-memory session. No disk, no database."""
    return Session(
        topic=topic,
        personas=personas,
        status=SessionStatus.IDLE,
    )

