import os
import pytest
from chamber.config import Config, DEFAULT_CLOUD_API_URL


def test_config_defaults():
    c = Config()
    assert c.provider == "ollama"
    assert c.model is None
    assert c.agents == 3
    assert c.rounds == 3
    assert c.ollama_url == "http://localhost:11434"
    assert c.cloud_api_url == DEFAULT_CLOUD_API_URL
    assert c.depth == "standard"


def test_config_from_kwargs():
    c = Config(provider="ollama", model="phi-3", agents=5, rounds=5)
    assert c.provider == "ollama"
    assert c.model == "phi-3"
    assert c.agents == 5
    assert c.rounds == 5


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("CHAMBER_PROVIDER", "ollama")
    monkeypatch.setenv("CHAMBER_MODEL", "mistral")
    monkeypatch.setenv("CHAMBER_AGENTS", "4")
    monkeypatch.setenv("CHAMBER_ROUNDS", "2")
    c = Config.from_env()
    assert c.provider == "ollama"
    assert c.model == "mistral"
    assert c.agents == 4
    assert c.rounds == 2


def test_config_env_defaults(monkeypatch):
    for key in ["CHAMBER_PROVIDER", "CHAMBER_MODEL", "CHAMBER_AGENTS", "CHAMBER_ROUNDS", "CHAMBER_CLOUD_URL"]:
        monkeypatch.delenv(key, raising=False)
    c = Config.from_env()
    assert c.provider == "ollama"
    assert c.model is None
    assert c.cloud_api_url == DEFAULT_CLOUD_API_URL


def test_config_kwargs_override_env(monkeypatch):
    monkeypatch.setenv("CHAMBER_PROVIDER", "ollama")
    c = Config.from_env(provider="ollama")
    assert c.provider == "ollama"


def test_cloud_api_url_env_override(monkeypatch):
    monkeypatch.setenv("CHAMBER_CLOUD_URL", "http://localhost:8000/api/v1/share")
    c = Config.from_env()
    assert c.cloud_api_url == "http://localhost:8000/api/v1/share"
