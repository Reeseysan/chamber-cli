import pytest
from click.testing import CliRunner

from chamber import __version__
from chamber.cli import main


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


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


def test_cli_depth_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert "--depth" in result.output


def test_cli_persona_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert "--persona" in result.output


def test_cli_personas_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert "--personas" in result.output


def test_cli_doc_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert "--doc" in result.output
