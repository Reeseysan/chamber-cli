from __future__ import annotations

from typing import Callable

from chamber.providers.base import LLMProvider

# Registry: name -> factory function
registry: dict[str, Callable[..., LLMProvider]] = {}


def register_provider(name: str, factory: Callable[..., LLMProvider]) -> None:
    """Register a provider factory by name."""
    registry[name] = factory


def get_provider(name: str, **kwargs) -> LLMProvider:
    """Create a provider instance by name."""
    if name not in registry:
        raise KeyError(f"Unknown provider: {name!r}. Available: {list(registry.keys())}")
    return registry[name](**kwargs)


def discover_providers() -> list[str]:
    """Return names of all registered providers."""
    return list(registry.keys())
