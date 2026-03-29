import pytest

from chamber.repl import parse_command, Command


def test_parse_follow():
    cmd = parse_command("/follow What about privacy?")
    assert cmd.name == "follow"
    assert cmd.args == "What about privacy?"


def test_parse_rounds():
    cmd = parse_command("/rounds 5")
    assert cmd.name == "rounds"
    assert cmd.args == "5"


def test_parse_agents():
    cmd = parse_command("/agents")
    assert cmd.name == "agents"
    assert cmd.args == ""


def test_parse_export():
    cmd = parse_command("/export")
    assert cmd.name == "export"
    assert cmd.args == ""


def test_parse_export_encrypt():
    cmd = parse_command("/export --encrypt")
    assert cmd.name == "export"
    assert cmd.args == "--encrypt"


def test_parse_save():
    cmd = parse_command("/save output.md")
    assert cmd.name == "save"
    assert cmd.args == "output.md"


def test_parse_new():
    cmd = parse_command("/new")
    assert cmd.name == "new"


def test_parse_status():
    cmd = parse_command("/status")
    assert cmd.name == "status"


def test_parse_quit():
    cmd = parse_command("/quit")
    assert cmd.name == "quit"


def test_parse_help():
    cmd = parse_command("/help")
    assert cmd.name == "help"


def test_parse_topic_input():
    cmd = parse_command("What are the legal risks?")
    assert cmd.name == "topic"
    assert cmd.args == "What are the legal risks?"


def test_parse_empty_input():
    cmd = parse_command("")
    assert cmd.name == "empty"


def test_parse_unknown_command():
    cmd = parse_command("/unknown thing")
    assert cmd.name == "unknown"
    assert cmd.args == "thing"
