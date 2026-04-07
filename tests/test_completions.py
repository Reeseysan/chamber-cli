"""Tests for completions module."""
from __future__ import annotations

import os
from unittest.mock import patch

from chamber.completions import detect_shell, _INSTRUCTIONS


def test_detect_shell_zsh():
    with patch.dict(os.environ, {"SHELL": "/bin/zsh"}, clear=False):
        assert detect_shell() == "zsh"


def test_detect_shell_bash():
    with patch.dict(os.environ, {"SHELL": "/bin/bash"}, clear=False):
        assert detect_shell() == "bash"


def test_detect_shell_fish():
    with patch.dict(os.environ, {"SHELL": "/usr/local/bin/fish"}, clear=False):
        assert detect_shell() == "fish"


def test_detect_shell_fallback():
    with patch.dict(os.environ, {"SHELL": "/bin/sh"}, clear=False):
        # Should fall back to bash
        result = detect_shell()
        assert result == "bash"


def test_instructions_have_all_shells():
    assert "bash" in _INSTRUCTIONS
    assert "zsh" in _INSTRUCTIONS
    assert "fish" in _INSTRUCTIONS


def test_instructions_have_eval_cmd():
    for shell, info in _INSTRUCTIONS.items():
        assert "eval_cmd" in info
        assert "setup" in info
        assert "file" in info
