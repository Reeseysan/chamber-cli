import pytest
from chamber.config import Config, get_word_limit, get_summary_limit


def test_config_depth_default():
    c = Config()
    assert c.depth == "standard"


def test_config_depth_from_env(monkeypatch):
    monkeypatch.setenv("CHAMBER_DEPTH", "deep")
    c = Config.from_env()
    assert c.depth == "deep"


def test_config_depth_from_kwarg():
    c = Config.from_env(depth="brief")
    assert c.depth == "brief"


def test_word_limit_brief():
    assert get_word_limit("brief", 1) == 100
    assert get_word_limit("brief", 2) == 150
    assert get_word_limit("brief", 3) == 200
    assert get_word_limit("brief", 5) == 200


def test_word_limit_standard():
    assert get_word_limit("standard", 1) == 200
    assert get_word_limit("standard", 2) == 350
    assert get_word_limit("standard", 3) == 500


def test_word_limit_deep():
    assert get_word_limit("deep", 1) == 400
    assert get_word_limit("deep", 2) == 600
    assert get_word_limit("deep", 3) == 800


def test_summary_limit():
    assert get_summary_limit("brief") == 100
    assert get_summary_limit("standard") == 200
    assert get_summary_limit("deep") == 300
