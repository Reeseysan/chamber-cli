from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Persona(BaseModel):
    name: str
    role: str
    expertise: str
    avatar_emoji: str
    system_prompt: str = ""


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    agent_name: str
    role: str  # "expert" | "moderator" | "user" | "system"
    content: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    round_number: int = 0


class ConsensusResult(BaseModel):
    reached: bool = False
    summary: str = ""
    key_points: list[str] = []
    dissenting_views: list[str] = []


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    personas: list[Persona] = []
    messages: list[Message] = []
    document_context: str = ""
    current_round: int = 0
    status: str = "idle"
