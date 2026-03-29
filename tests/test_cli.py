import pytest
from click.testing import CliRunner

from chamber.cli import main


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--provider" in result.output
    assert "--model" in result.output
    assert "--agents" in result.output
    assert "--rounds" in result.output


def test_cli_one_shot_requires_topic():
    runner = CliRunner()
    result = runner.invoke(main, ["--one-shot"])
    assert result.exit_code != 0 or "No topic" in result.output or "Missing" in result.output
