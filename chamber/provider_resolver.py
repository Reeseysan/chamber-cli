"""Provider resolution logic — extracted from cli.py.

Handles auto-detection of local providers, fallback to remote providers,
and provider-specific configuration.
"""
from __future__ import annotations

import sys
import os

import click
import httpx

from chamber.config import Config
from chamber.providers import get_provider, discover_providers
from chamber.providers.base import LLMProvider


def _try_import(module: str) -> None:
    """Try to import a module, silently ignore failures."""
    try:
        __import__(module)
    except (ImportError, ValueError):
        pass


def import_all_providers() -> None:
    """Import all provider modules to trigger registration."""
    import chamber.providers.ollama  # noqa: F401
    _try_import("chamber.providers.openai")
    _try_import("chamber.providers.anthropic")
    _try_import("chamber.providers.openrouter")


def resolve_provider(config: Config, explicit_provider: str | None) -> LLMProvider:
    """Resolve the LLM provider — try explicit, then local, then remote.

    Args:
        config: The application config.
        explicit_provider: Provider name from --provider flag (None if not set).

    Returns:
        A configured LLMProvider instance.
    """
    import_all_providers()

    if explicit_provider is not None:
        return _resolve_explicit(config)

    # Auto-detect: try local first, then remote
    llm = _try_local_providers(config)
    if llm is not None:
        return llm

    llm = _try_remote_providers(config)
    if llm is not None:
        return llm

    click.echo(
        "No model server or API key detected.\n"
        f"  Ollama:     not running at {config.ollama_url}\n\n"
        "Local:  Install Ollama (https://ollama.com)\n"
        "Remote: Set CHAMBER_OPENAI_API_KEY, CHAMBER_ANTHROPIC_API_KEY,\n"
        "        or CHAMBER_OPENROUTER_API_KEY in your environment.\n",
        err=True,
    )
    sys.exit(1)


def _resolve_explicit(config: Config) -> LLMProvider:
    """Resolve an explicitly named provider."""
    kwargs = {"model": config.model} if config.model else {}
    if config.provider == "ollama":
        kwargs["base_url"] = config.ollama_url
    if config.proxy:
        kwargs["proxy"] = config.proxy
    try:
        return get_provider(config.provider, **kwargs)
    except KeyError:
        available = ", ".join(discover_providers())
        click.echo(f"Unknown provider: {config.provider}. Available: {available}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


def _try_local_providers(config: Config) -> LLMProvider | None:
    """Try to connect to local providers (Ollama)."""
    try:
        httpx.get(f"{config.ollama_url}/", timeout=3)
    except (httpx.ConnectError, httpx.TimeoutException):
        return None

    kwargs: dict = {"base_url": config.ollama_url}
    if config.model:
        kwargs["model"] = config.model
    llm = get_provider("ollama", **kwargs)
    config.provider = "ollama"
    config.model = getattr(llm, "model", config.model)
    return llm


def _try_remote_providers(config: Config) -> LLMProvider | None:
    """Try remote providers that have API keys set."""
    remote_options = [
        ("openai", "CHAMBER_OPENAI_API_KEY"),
        ("anthropic", "CHAMBER_ANTHROPIC_API_KEY"),
        ("openrouter", "CHAMBER_OPENROUTER_API_KEY"),
    ]
    for name, env_key in remote_options:
        if os.environ.get(env_key):
            try:
                kwargs: dict = {}
                if config.model:
                    kwargs["model"] = config.model
                if config.proxy:
                    kwargs["proxy"] = config.proxy
                llm = get_provider(name, **kwargs)
                config.provider = name
                config.model = getattr(llm, "model", config.model)
                return llm
            except (KeyError, ValueError):
                continue
    return None


# Moved here so /provider in REPL can use the same logic
LOCAL_PROVIDERS = {"ollama"}
REMOTE_PROVIDER_KEYS = {
    "openai": "CHAMBER_OPENAI_API_KEY",
    "anthropic": "CHAMBER_ANTHROPIC_API_KEY",
    "openrouter": "CHAMBER_OPENROUTER_API_KEY",
}
