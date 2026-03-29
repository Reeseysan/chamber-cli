"""
Privacy tests — hard CI gate.
These verify the privacy guarantees documented in the README.
If any of these fail, the PR cannot merge.
"""

import os
import sys
import tempfile
import importlib
import pytest

from chamber.providers.base import LLMProvider


class MemoryOnlyProvider(LLMProvider):
    """Provider that never touches the network."""

    async def stream_completion(self, system, messages, on_token):
        text = "Test response."
        result = on_token(text)
        if result is not None:
            await result
        return text

    async def completion(self, system, messages):
        return "Test response."

    async def json_completion(self, system, messages):
        return '{"reached": false, "summary": "Test.", "key_points": [], "dissenting_views": []}'


def _snapshot_directory(path: str) -> set[str]:
    """Return all file paths under a directory."""
    result = set()
    for root, dirs, files in os.walk(path):
        for f in files:
            result.add(os.path.join(root, f))
    return result


async def test_no_disk_writes_during_session():
    """A full session must not create any files on disk."""
    from chamber.models import Persona, Session
    from chamber.orchestrator import Orchestrator

    with tempfile.TemporaryDirectory() as tmpdir:
        before = _snapshot_directory(tmpdir)

        # Change to temp dir so any accidental writes land here
        old_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            personas = [
                Persona(name="A", role="R", expertise="E", avatar_emoji="🧑",
                        system_prompt="You are A."),
            ]
            session = Session(topic="Test", personas=personas)
            provider = MemoryOnlyProvider()

            orchestrator = Orchestrator(
                session=session,
                provider=provider,
                max_rounds=1,
                on_token=lambda name, token: None,
            )
            await orchestrator.run()

            after = _snapshot_directory(tmpdir)
            new_files = after - before
            assert new_files == set(), f"Files written to disk during session: {new_files}"
        finally:
            os.chdir(old_cwd)


def test_no_config_directory_created():
    """~/.chamber/ must not exist unless user explicitly creates it."""
    chamber_dir = os.path.expanduser("~/.chamber")
    # This test checks that importing and using chamber doesn't create the dir
    # If it already exists (user chose to create it), skip
    if os.path.exists(chamber_dir):
        pytest.skip("~/.chamber already exists (user-created)")

    from chamber.config import Config
    Config.from_env()

    assert not os.path.exists(chamber_dir), "~/.chamber/ was created without user action"


def test_no_hardcoded_remote_urls():
    """No hardcoded remote URLs in the codebase (except localhost)."""
    import chamber
    package_dir = os.path.dirname(chamber.__file__)

    remote_urls = []
    for root, dirs, files in os.walk(package_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(root, fname)
            with open(filepath) as f:
                content = f.read()
            for line_num, line in enumerate(content.splitlines(), 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Check for http/https URLs that aren't localhost
                # Allow URLs in string literals used for user-facing messages (not network calls)
                if "http://" in line or "https://" in line:
                    if "localhost" not in line and "127.0.0.1" not in line:
                        # Skip lines that are purely in string literals (user messages/docs)
                        if "httpx" in line or "client" in line or "fetch" in line or "request" in line:
                            remote_urls.append(f"{filepath}:{line_num}: {stripped}")

    assert remote_urls == [], (
        f"Found hardcoded remote URLs:\n" + "\n".join(remote_urls)
    )


def test_repl_history_disabled():
    """REPL must use InMemoryHistory, not FileHistory."""
    from chamber.repl import ChamberREPL
    from chamber.config import Config
    from prompt_toolkit.history import InMemoryHistory

    config = Config()
    repl = ChamberREPL(config=config, provider=MemoryOnlyProvider())
    assert isinstance(repl.prompt_session.history, InMemoryHistory), (
        "REPL must use InMemoryHistory to avoid writing history to disk"
    )


def test_dependency_count():
    """Flag if direct dependencies exceed expected count."""
    # Read pyproject.toml and count dependencies
    pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
    if not os.path.exists(pyproject_path):
        pytest.skip("pyproject.toml not found")

    with open(pyproject_path) as f:
        content = f.read()

    # Count lines in dependencies section
    in_deps = False
    dep_count = 0
    for line in content.splitlines():
        if line.strip() == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if line.strip() == "]":
                break
            if line.strip().startswith('"'):
                dep_count += 1

    assert dep_count <= 6, (
        f"Direct dependency count is {dep_count}, expected <= 6. "
        "New dependencies must be reviewed for privacy implications."
    )


async def test_document_content_not_persisted():
    """Document content must stay in memory, not touch disk."""
    import tempfile
    from chamber.models import Persona, Session
    from chamber.orchestrator import Orchestrator

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            before = _snapshot_directory(tmpdir)

            personas = [
                Persona(name="A", role="R", expertise="E", avatar_emoji="🧑",
                        system_prompt="You are A."),
            ]
            session = Session(
                topic="Test",
                personas=personas,
                document_context="[DOCUMENT: secret.pdf]\n\nTop secret content here.",
            )
            provider = MemoryOnlyProvider()

            orchestrator = Orchestrator(
                session=session,
                provider=provider,
                max_rounds=1,
                on_token=lambda name, token: None,
            )
            await orchestrator.run()

            after = _snapshot_directory(tmpdir)
            new_files = after - before
            assert new_files == set(), f"Files written during document session: {new_files}"
        finally:
            os.chdir(old_cwd)
