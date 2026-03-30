from __future__ import annotations

import sys
import asyncio
from dataclasses import dataclass

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory

from chamber import __version__
from chamber.config import Config
from chamber.models import Session, ConsensusResult
from chamber.session import create_session
from chamber.persona import generate_personas
from chamber.orchestrator import Orchestrator
from chamber.export import export_markdown, export_encrypted
from chamber.providers.base import LLMProvider
from chamber.document import load_document, DocumentError

VALID_COMMANDS = {"follow", "rounds", "agents", "export", "save", "new", "status", "quit", "help", "depth", "doc", "update", "provider", "model"}

class _SlashCompleter(Completer):
    """Show slash commands as you type — only activates when input starts with /."""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if not text.startswith("/"):
            return
        partial = text[1:].lower()
        for cmd in sorted(VALID_COMMANDS):
            if cmd.startswith(partial):
                yield Completion(f"/{cmd}", start_position=-len(text))

HELP_TEXT = """
Commands:
  /follow <text>      Inject a follow-up into the next round
  /rounds <n>         Set max rounds for this session
  /depth <level>      Set depth: brief, standard, deep
  /doc <path>         Load a document into the session
  /agents             List current panel members
  /export             Export session as markdown to stdout
  /export --encrypt   Export with passphrase encryption
  /save <path>        Write export to a file
  /provider [name]    Switch provider (ollama, lmstudio) or show current
  /model [name]       Switch model or show current
  /new                Clear session, start fresh topic
  /status             Show provider, model, session stats
  /update             Check for updates and install latest version
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
        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            completer=_SlashCompleter(),
            complete_while_typing=True,
        )

    def _print(self, text: str = "") -> None:
        print(text, flush=True)

    def _print_token(self, agent_name: str, token: str) -> None:
        sys.stdout.write(token)
        sys.stdout.flush()

    def _print_banner(self) -> None:
        self._print(f"Chamber CLI v{__version__} — Private expert panels in your terminal.")
        model_name = self.config.model or getattr(self.provider, "model", None) or "default"
        self._print(f"Provider: {self.config.provider} ({model_name})")
        self._print()
        self._print("  Privacy: No data leaves your machine. No telemetry. No account required.")
        self._print("           All processing is local. Nothing is written to disk.")
        self._print()
        self._print("  Note:    Outputs are AI-generated for informational purposes only.")
        self._print("           Not legal, financial, medical, or professional advice.")
        self._print()
        self._print("Type /help for commands.")
        self._print()

    async def _handle_topic(self, topic: str) -> None:
        self._print()
        self._print("Generating panel...")
        from chamber.config import get_word_limit
        word_limit = get_word_limit(self.config.depth, 1)
        personas = await generate_personas(topic, self.provider, count=self.config.agents, word_limit=word_limit)
        self.session = create_session(topic, personas)

        panel_names = ", ".join(p.name for p in personas)
        self._print(f"Panel: {panel_names}")
        self._print()

        self.orchestrator = Orchestrator(
            session=self.session,
            provider=self.provider,
            max_rounds=self.config.rounds,
            depth=self.config.depth,
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
            self._print(f"Model: {getattr(self.provider, 'model', self.config.model) or 'default'}")
            self._print(f"Depth: {self.config.depth}")
            if self.session:
                self._print(f"Topic: {self.session.topic}")
                self._print(f"Messages: {len(self.session.messages)}")
                self._print(f"Round: {self.session.current_round}")
                if self.session.document_context:
                    self._print(f"Documents loaded: yes")
            else:
                self._print("No active session.")
            return False

        if cmd.name == "provider":
            name = cmd.args.strip().lower()
            if not name:
                self._print(f"Current: {self.config.provider} ({getattr(self.provider, 'model', 'default')})")
                self._print("Available: ollama, lmstudio")
                self._print("Usage: /provider ollama  or  /provider lmstudio")
                return False
            if name not in ("ollama", "lmstudio"):
                self._print(f"Unknown provider '{name}'. Available: ollama, lmstudio")
                return False
            import httpx
            from chamber.providers import get_provider
            from chamber.config import is_localhost
            url = self.config.ollama_url if name == "ollama" else self.config.lmstudio_url
            if not is_localhost(url):
                self._print(f"WARNING: {url} is not localhost. Data will leave your machine.")
                self._print("The privacy guarantee only applies to local providers.")
            check_url = f"{url}/" if name == "ollama" else f"{url}/v1/models"
            try:
                resp = httpx.get(check_url, timeout=3)
                kwargs = {"base_url": url}
                # Auto-detect model
                if name == "lmstudio":
                    try:
                        models = resp.json().get("data", [])
                        if models:
                            kwargs["model"] = models[0].get("id", "local-model")
                    except Exception:
                        pass
                elif name == "ollama" and self.config.model:
                    kwargs["model"] = self.config.model
                self.provider = get_provider(name, **kwargs)
                self.config.provider = name
                self.config.model = getattr(self.provider, "model", None)
                self._print(f"Switched to {name} ({self.config.model or 'default'})")
            except (httpx.ConnectError, httpx.TimeoutException):
                self._print(f"{name} is not running at {url}")
                if name == "lmstudio":
                    self._print("Start the server: LM Studio → Developer → Start Server")
                else:
                    self._print("Start Ollama: ollama serve")
            return False

        if cmd.name == "model":
            name = cmd.args.strip()
            if not name:
                self._print(f"Current model: {getattr(self.provider, 'model', 'default')}")
                self._print("Usage: /model <model-name>")
                return False
            self.provider.model = name
            self.config.model = name
            self._print(f"Model set to {name}")
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

        if cmd.name == "depth":
            level = cmd.args.strip().lower()
            if level not in ("brief", "standard", "deep"):
                self._print("Usage: /depth brief|standard|deep")
                return False
            self.config.depth = level
            self._print(f"Depth set to {level}.")
            return False

        if cmd.name == "doc":
            path = cmd.args.strip()
            if not path:
                self._print("Usage: /doc <path>")
                return False
            try:
                doc_text = load_document(path)
                if self.session:
                    if self.session.document_context:
                        self.session.document_context += "\n\n" + doc_text
                    else:
                        self.session.document_context = doc_text
                    word_count = len(doc_text.split())
                    self._print(f"Document loaded: {path} ({word_count:,} words)")
                else:
                    self._print("No active session. Start a topic first, then load documents.")
            except DocumentError as e:
                self._print(f"Error: {e}")
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
            import os
            if os.path.exists(path):
                confirm = await self.prompt_session.prompt_async(
                    f"File '{path}' already exists. Overwrite? [y/N] "
                )
                if confirm.strip().lower() not in ("y", "yes"):
                    self._print("Cancelled.")
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

        if cmd.name == "update":
            import subprocess
            self._print(f"Current version: v{__version__}")
            self._print("Checking for updates...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "chamber-cli"],
                    capture_output=True, text=True, timeout=30,
                )
                if "Successfully installed" in result.stdout:
                    new_ver = ""
                    for line in result.stdout.splitlines():
                        if "chamber-cli" in line.lower():
                            new_ver = line.strip()
                    self._print(f"Updated. {new_ver}")
                    self._print("Restart chamber to use the new version.")
                else:
                    self._print(f"Already on the latest version (v{__version__}).")
            except subprocess.TimeoutExpired:
                self._print("Update timed out. Try: pip install --upgrade chamber-cli")
            except Exception as e:
                self._print(f"Update failed: {e}")
                self._print("Try manually: pip install --upgrade chamber-cli")
            return False

        if cmd.name == "unknown":
            cmds = " ".join(f"/{c}" for c in sorted(VALID_COMMANDS))
            self._print(f"Unknown command. Available: {cmds}")
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
