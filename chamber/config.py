from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

WORD_LIMITS = {
    "brief":    {1: 100, 2: 150},
    "standard": {1: 200, 2: 350},
    "deep":     {1: 400, 2: 600},
}

WORD_LIMIT_DEFAULT = {
    "brief": 200,
    "standard": 500,
    "deep": 800,
}

SUMMARY_LIMITS = {
    "brief": 100,
    "standard": 200,
    "deep": 300,
}


def get_word_limit(depth: str, round_number: int) -> int:
    """Get word limit for a given depth and round number."""
    limits = WORD_LIMITS.get(depth, WORD_LIMITS["standard"])
    return limits.get(round_number, WORD_LIMIT_DEFAULT.get(depth, 500))


def get_summary_limit(depth: str) -> int:
    """Get moderator summary word limit for a given depth."""
    return SUMMARY_LIMITS.get(depth, 200)


_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}

# Providers that send data over the network
REMOTE_PROVIDERS = {"openai", "anthropic", "openrouter"}


def is_localhost(url: str) -> bool:
    """Check if a URL points to a local address."""
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower() in _LOCALHOST_HOSTS
    except Exception:
        return False


def is_remote_provider(provider: str) -> bool:
    """Check if a provider sends data over the network."""
    return provider in REMOTE_PROVIDERS


@dataclass
class Config:
    provider: str = "ollama"
    model: str | None = None
    agents: int = 3
    rounds: int = 3
    depth: str = "standard"
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
            "depth": os.environ.get("CHAMBER_DEPTH", "standard"),
            "ollama_url": os.environ.get("CHAMBER_OLLAMA_URL", "http://localhost:11434"),
            "lmstudio_url": os.environ.get("CHAMBER_LMSTUDIO_URL", "http://localhost:1234"),
            "proxy": os.environ.get("CHAMBER_PROXY"),
        }
        for key, value in overrides.items():
            if value is not None:
                env_values[key] = value

        config = cls(**env_values)

        # Warn if any provider URL points to a non-localhost address
        for name, url in [("Ollama", config.ollama_url), ("LM Studio", config.lmstudio_url)]:
            if not is_localhost(url):
                print(
                    f"\n  WARNING: {name} URL points to a remote host ({url}).\n"
                    f"  Data WILL be sent over the network. The privacy guarantee\n"
                    f"  only applies when using localhost providers.\n",
                    file=sys.stderr,
                )

        # Warn if using a remote provider
        if is_remote_provider(config.provider):
            print(
                f"\n  NOTICE: Using remote provider '{config.provider}'.\n"
                f"  Your discussion data will be sent to a third-party API.\n"
                f"  The local-only privacy guarantee does not apply.\n",
                file=sys.stderr,
            )

        return config
