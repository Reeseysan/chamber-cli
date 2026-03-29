from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    provider: str = "ollama"
    model: str | None = None
    agents: int = 3
    rounds: int = 3
    ollama_url: str = "http://localhost:11434"
    lmstudio_url: str = "http://localhost:1234"
    proxy: str | None = None

    @classmethod
    def from_env(cls, **overrides) -> Config:
        """Build config from environment variables, with kwargs taking precedence."""
        env_values = {
            "provider": os.environ.get("CHAMBER_PROVIDER", "ollama"),
            "model": os.environ.get("CHAMBER_MODEL"),
            "agents": int(os.environ.get("CHAMBER_AGENTS", "3")),
            "rounds": int(os.environ.get("CHAMBER_ROUNDS", "3")),
            "ollama_url": os.environ.get("CHAMBER_OLLAMA_URL", "http://localhost:11434"),
            "lmstudio_url": os.environ.get("CHAMBER_LMSTUDIO_URL", "http://localhost:1234"),
            "proxy": os.environ.get("CHAMBER_PROXY"),
        }
        # kwargs override env
        for key, value in overrides.items():
            if value is not None:
                env_values[key] = value
        return cls(**env_values)
