import os
import pytest
from chamber.config import Config


def test_config_defaults():
    c = Config()
    assert c.provider == "ollama"
    assert c.model is None
    assert c.agents == 3
    assert c.rounds == 3
    assert c.ollama_url == "http://localhost:11434"
    assert c.lmstudio_url == "http://localhost:1234"
    assert c.proxy is None


def test_config_from_kwargs():
    c = Config(provider="lmstudio", model="phi-3", agents=5, rounds=5)
    assert c.provider == "lmstudio"
    assert c.model == "phi-3"
    assert c.agents == 5
    assert c.rounds == 5


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("CHAMBER_PROVIDER", "lmstudio")
    monkeypatch.setenv("CHAMBER_MODEL", "mistral")
    monkeypatch.setenv("CHAMBER_AGENTS", "4")
    monkeypatch.setenv("CHAMBER_ROUNDS", "2")
    monkeypatch.setenv("CHAMBER_PROXY", "socks5://localhost:9050")
    c = Config.from_env()
    assert c.provider == "lmstudio"
    assert c.model == "mistral"
    assert c.agents == 4
    assert c.rounds == 2
    assert c.proxy == "socks5://localhost:9050"


def test_config_env_defaults(monkeypatch):
    for key in ["CHAMBER_PROVIDER", "CHAMBER_MODEL", "CHAMBER_AGENTS", "CHAMBER_ROUNDS", "CHAMBER_PROXY"]:
        monkeypatch.delenv(key, raising=False)
    c = Config.from_env()
    assert c.provider == "ollama"
    assert c.model is None


def test_config_kwargs_override_env(monkeypatch):
    monkeypatch.setenv("CHAMBER_PROVIDER", "lmstudio")
    c = Config.from_env(provider="ollama")
    assert c.provider == "ollama"
