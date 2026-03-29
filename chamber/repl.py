from __future__ import annotations

import sys
import asyncio
from dataclasses import dataclass

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from chamber import __version__
from chamber.config import Config
from chamber.models import Session, ConsensusResult
from chamber.session import create_session
from chamber.persona import generate_personas
from chamber.orchestrator import Orchestrator
from chamber.export import export_markdown, export_encrypted
from chamber.providers.base import LLMProvider

VALID_COMMANDS = {"follow", "rounds", "agents", "export", "save", "new", "status", "quit", "help"}

HELP_TEXT = """
Commands:
  /follow <text>      Inject a follow-up into the next round
  /rounds <n>         Set max rounds for this session
  /agents             List current panel members
  /export             Export session as markdown to stdout
  /export --encrypt   Export with passphrase encryption
  /save <path>        Write export to a file
  /new                Clear session, start fresh topic
  /status             Show provider, model, session stats
  /help               Show this help
  /quit               Exit (session is destroyed)
""".strip()


@dataclass
class Command:
    name: str
    args: str = ""


def parse_command(text: str) -> Command:
    """Parse user input into a Command."""
    text = text.strip()
    if not text:
        return Command(name="empty")
    if not text.startswith("/"):
        return Command(name="topic", args=text)

    parts = text[1:].split(maxsplit=1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if name not in VALID_COMMANDS:
        return Command(name="unknown", args=args)

    return Command(name=name, args=args)


class ChamberREPL:
    def __init__(self, config: Config, provider: LLMProvider):
        self.config = config
        self.provider = provider
        self.session: Session | None = None
        self.orchestrator: Orchestrator | None = None
        self.prompt_session = PromptSession(history=InMemoryHistory())

    def _print(self, text: str = "") -> None:
        print(text, flush=True)

    def _print_token(self, agent_name: str, token: str) -> None:
        sys.stdout.write(token)
        sys.stdout.flush()

    def _print_banner(self) -> None:
        self._print(f"Chamber CLI v{__version__} — Private expert panels in your terminal.")
        self._print(f"Provider: {self.config.provider} ({self.config.model or 'default'})")
        self._print("No data is written to disk. Type /help for commands.")
        self._print()

    async def _handle_topic(self, topic: str) -> None:
        self._print()
        self._print("Generating panel...")
        personas = await generate_personas(topic, self.provider, count=self.config.agents)
        self.session = create_session(topic, personas)

        panel_names = ", ".join(p.name for p in personas)
        self._print(f"Panel: {panel_names}")
        self._print()

        self.orchestrator = Orchestrator(
            session=self.session,
            provider=self.provider,
            max_rounds=self.config.rounds,
            on_token=self._print_token,
            on_round_start=lambda r: self._print(f"\n{'─' * 2} Round {r} {'─' * 48}\n"),
            on_agent_start=lambda name: self._print(f"[{name}]"),
            on_agent_done=lambda name, text: self._print("\n"),
            on_moderator=lambda text: (self._print(f"{'─' * 2} Moderator {'─' * 45}"), self._print(text), self._print()),
            on_consensus=lambda result: self._print_consensus(result),
        )

        await self.orchestrator.run()

    def _print_consensus(self, result: ConsensusResult) -> None:
        self._print(f"\n{'═' * 56}")
        if result.reached:
            self._print("CONSENSUS REACHED")
        else:
            self._print("DISCUSSION ENDED (no full consensus)")
        self._print(f"{'═' * 56}")
        self._print(result.summary)
        if result.key_points:
            self._print("\nKey points:")
            for point in result.key_points:
                self._print(f"  - {point}")
        if result.dissenting_views:
            self._print("\nDissenting views:")
            for view in result.dissenting_views:
                self._print(f"  - {view}")
        self._print()

    async def _handle_command(self, cmd: Command) -> bool:
        """Handle a command. Returns True if REPL should exit."""
        if cmd.name == "empty":
            return False

        if cmd.name == "quit":
            return True

        if cmd.name == "help":
            self._print(HELP_TEXT)
            return False

        if cmd.name == "topic":
            await self._handle_topic(cmd.args)
            return False

        if cmd.name == "new":
            self.session = None
            self.orchestrator = None
            self._print("Session cleared. Enter a new topic.")
            return False

        if cmd.name == "status":
            self._print(f"Provider: {self.config.provider}")
            self._print(f"Model: {self.config.model or 'default'}")
            if self.session:
                self._print(f"Topic: {self.session.topic}")
                self._print(f"Messages: {len(self.session.messages)}")
                self._print(f"Round: {self.session.current_round}")
            else:
                self._print("No active session.")
            return False

        if cmd.name == "agents":
            if not self.session:
                self._print("No active session.")
                return False
            for p in self.session.personas:
                self._print(f"  {p.avatar_emoji} {p.name} — {p.role}")
            return False

        if cmd.name == "rounds":
            try:
                n = int(cmd.args)
                self.config.rounds = min(max(n, 1), 5)
                self._print(f"Max rounds set to {self.config.rounds}.")
            except ValueError:
                self._print("Usage: /rounds <number>")
            return False

        if cmd.name == "export":
            if not self.session:
                self._print("No active session to export.")
                return False
            md = export_markdown(self.session)
            if "--encrypt" in cmd.args:
                passphrase = await self.prompt_session.prompt_async("Passphrase: ", is_password=True)
                encrypted = export_encrypted(md, passphrase)
                sys.stdout.buffer.write(encrypted)
                self._print("\n(Encrypted export written to stdout)")
            else:
                self._print(md)
            return False

        if cmd.name == "save":
            if not self.session:
                self._print("No active session to save.")
                return False
            path = cmd.args.strip()
            if not path:
                self._print("Usage: /save <path>")
                return False
            md = export_markdown(self.session)
            with open(path, "w") as f:
                f.write(md)
            self._print(f"Saved to {path}")
            return False

        if cmd.name == "follow":
            if not self.orchestrator or not self.session:
                self._print("No active session. Enter a topic first.")
                return False
            self.orchestrator.inject_user_message(cmd.args)
            self._print("Follow-up queued. Starting next round...")
            await self.orchestrator.run()
            return False

        if cmd.name == "unknown":
            self._print(f"Unknown command. Type /help for available commands.")
            return False

        return False

    async def run(self) -> None:
        """Main REPL loop."""
        self._print_banner()

        while True:
            try:
                text = await self.prompt_session.prompt_async("> ")
                cmd = parse_command(text)
                should_exit = await self._handle_command(cmd)
                if should_exit:
                    break
            except (KeyboardInterrupt, EOFError):
                break

        self._print("Session destroyed. Goodbye.")
