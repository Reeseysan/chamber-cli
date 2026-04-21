from __future__ import annotations

import sys
import asyncio

import click

from chamber import __version__
from chamber.config import Config, get_word_limit


@click.command()
@click.version_option(__version__, prog_name="Chamber CLI")
@click.argument("topic", required=False, default=None)
@click.option("--provider", default=None, help="Provider to use (ollama, openai, anthropic, openrouter)")
@click.option("--model", default=None, help="Model name to use")
@click.option("--agents", default=None, type=int, help="Number of expert agents (default: 3, max: 5)")
@click.option("--rounds", default=None, type=int, help="Max discussion rounds (default: 3, max: 5)")
@click.option("--depth", default=None, type=click.Choice(["brief", "standard", "deep"]), help="Discussion depth (default: standard)")
@click.option("--one-shot", is_flag=True, help="Run discussion and exit (no REPL)")
@click.option("--save", "save_path", default=None, help="Save export to file after discussion")
@click.option("--persona", "persona_roles", multiple=True, help="Expert role (repeatable)")
@click.option("--personas", "personas_file", default=None, help="Path to personas JSON file")
@click.option("--doc", "doc_paths", multiple=True, help="Document file to load (repeatable)")
@click.option("--template", "template_name", default=None, help="Use a preset panel template (e.g. legal-review, code-review)")
@click.option("--list-templates", is_flag=True, help="List available panel templates and exit")
@click.option("--format", "output_format", default="text", type=click.Choice(["text", "json"]), help="Output format (default: text)")
@click.option("--proxy", default=None, help="SOCKS5 proxy URL (e.g. socks5://localhost:9050)")
@click.option("--git-diff", is_flag=True, help="Ingest current git diff as document context")
@click.option("--git-staged", is_flag=True, help="Ingest staged git changes as document context")
@click.option("--git-pr", default=None, type=int, help="Ingest PR diff as document context (PR number)")
@click.option("--resume", "resume_path", default=None, help="Resume a previously exported session")
@click.option("--install-completions", is_flag=True, help="Print shell completion install instructions")
@click.option("--serve", is_flag=True, help="Start as MCP server (Model Context Protocol)")
def discuss(
    topic, provider, model, agents, rounds, depth, one_shot, save_path,
    persona_roles, personas_file, doc_paths, template_name, list_templates,
    output_format, proxy, git_diff, git_staged, git_pr, resume_path,
    install_completions, serve,
):
    """Chamber CLI — Private expert panels in your terminal."""

    # --- Early-exit commands ---

    if install_completions:
        from chamber.completions import install_completions as do_install
        do_install()
        return

    if list_templates:
        from chamber.templates import list_templates as get_templates
        templates = get_templates()
        if not templates:
            click.echo("No templates found.")
        else:
            click.echo("Available templates:\n")
            for t in templates:
                click.echo(f"  {t['name']:20s} {t['description']}")
            click.echo(f"\nUsage: chamber --template <name> \"your topic\"")
        return

    if serve:
        from chamber.mcp_server import run_mcp_server
        run_mcp_server()
        return

    # --- Validation ---

    if persona_roles and personas_file:
        click.echo("Cannot use both --persona and --personas. Pick one.", err=True)
        sys.exit(1)

    if template_name and (persona_roles or personas_file):
        click.echo("Cannot use --template with --persona/--personas. Pick one.", err=True)
        sys.exit(1)

    config = Config.from_env(
        provider=provider,
        model=model,
        agents=min(agents, 5) if agents else None,
        rounds=min(rounds, 5) if rounds else None,
        depth=depth,
        proxy=proxy,
    )

    # --- Provider setup ---

    from chamber.provider_resolver import resolve_provider
    llm = resolve_provider(config, provider)

    # --- Git-aware document ingestion ---

    document_context = _load_git_context(git_diff, git_staged, git_pr)
    if document_context and not template_name and not persona_roles and not personas_file:
        template_name = "code-review"
    if document_context and not topic:
        topic = "Review the following code changes"

    # --- Load documents ---

    document_context = _load_documents(doc_paths, document_context)
    document_context = _load_stdin(document_context)

    # --- Session resume ---

    if resume_path:
        asyncio.run(_resume(config, llm, resume_path, one_shot, output_format, save_path, document_context))
        return

    # --- Main flow ---

    if one_shot:
        if not topic:
            click.echo("No topic provided. Usage: chamber \"your topic\" --one-shot", err=True)
            sys.exit(1)
        asyncio.run(_one_shot(config, llm, topic, save_path, persona_roles, personas_file, document_context, template_name, output_format))
    else:
        asyncio.run(_repl(config, llm, topic, persona_roles, personas_file, document_context, template_name))


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _load_git_context(git_diff: bool, git_staged: bool, git_pr: int | None) -> str:
    """Load git diff as document context if any git flags are set."""
    if not (git_diff or git_staged or git_pr is not None):
        return ""

    from chamber.git import get_git_diff, get_git_pr_diff, GitError
    try:
        if git_pr is not None:
            return get_git_pr_diff(pr_number=git_pr)
        elif git_staged:
            return get_git_diff(staged=True)
        else:
            return get_git_diff(staged=False)
    except GitError as e:
        click.echo(f"Git error: {e}", err=True)
        sys.exit(1)


def _load_documents(doc_paths: tuple, existing_context: str) -> str:
    """Load document files and append to existing context."""
    if not doc_paths:
        return existing_context

    from chamber.document import load_document, DocumentError
    parts = []
    for path in doc_paths:
        try:
            parts.append(load_document(path))
        except DocumentError as e:
            click.echo(f"Error loading {path}: {e}", err=True)
            sys.exit(1)

    new_docs = "\n\n".join(parts)
    return f"{existing_context}\n\n{new_docs}".strip() if existing_context else new_docs


def _load_stdin(existing_context: str) -> str:
    """Load piped stdin content."""
    if sys.stdin.isatty():
        return existing_context

    from chamber.document import load_from_stdin, DocumentError
    try:
        stdin_doc = load_from_stdin(sys.stdin)
        return f"{existing_context}\n\n{stdin_doc}".strip() if existing_context else stdin_doc
    except DocumentError:
        return existing_context


# ---------------------------------------------------------------------------
# Persona resolution
# ---------------------------------------------------------------------------

def _get_personas(config, provider, topic, persona_roles, personas_file, template_name, word_limit):
    """Resolve personas from template, file, roles, or auto-generate.
    
    Returns (personas, is_sync). If is_sync is False, caller must await generation.
    """
    if template_name:
        from chamber.templates import load_template, template_to_personas
        tmpl = load_template(template_name)
        personas = template_to_personas(tmpl, word_limit)
        overrides = tmpl.get("config_overrides", {})
        for key, val in overrides.items():
            if hasattr(config, key):
                setattr(config, key, val)
        return personas, True

    if personas_file:
        from chamber.persona import load_personas_from_file
        return load_personas_from_file(personas_file), True

    return None, False  # needs async generation


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

async def _one_shot(config, provider, topic, save_path, persona_roles, personas_file, document_context, template_name, output_format):
    from chamber.persona import generate_personas, generate_personas_from_roles
    from chamber.session import create_session
    from chamber.orchestrator import Orchestrator
    from chamber.export import export_markdown
    from chamber.formatters import format_session_json
    from chamber.output import make_text_callbacks, make_silent_callbacks, get_last_consensus
    from chamber.store import save_session

    word_limit = get_word_limit(config.depth, 1)
    is_json = output_format == "json"

    personas, is_sync = _get_personas(config, provider, topic, persona_roles, personas_file, template_name, word_limit)

    if personas is None:
        if persona_roles:
            if not is_json:
                print("Generating panel from roles...", flush=True)
            personas = await generate_personas_from_roles(
                roles=list(persona_roles), topic=topic, provider=provider, word_limit=word_limit
            )
        else:
            if not is_json:
                print("Generating panel...", flush=True)
            personas = await generate_personas(topic, provider, count=config.agents, word_limit=word_limit)

    session = create_session(topic, personas)
    session.document_context = document_context

    if not is_json:
        print(f"Panel: {', '.join(p.name for p in personas)}\n", flush=True)

    callbacks = make_silent_callbacks() if is_json else make_text_callbacks()

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=config.rounds,
        depth=config.depth,
        **{k: v for k, v in callbacks.items() if not k.startswith("_")},
    )

    await orchestrator.run()

    save_session(session)

    if is_json:
        print(format_session_json(session, get_last_consensus(callbacks)))
    elif save_path:
        md = export_markdown(session)
        with open(save_path, "w") as f:
            f.write(md)
        print(f"\nSaved to {save_path}", flush=True)


async def _resume(config, provider, resume_path, one_shot, output_format, save_path, extra_document_context):
    from chamber.resume import load_session_file
    from chamber.orchestrator import Orchestrator
    from chamber.export import export_markdown
    from chamber.formatters import format_session_json
    from chamber.output import make_text_callbacks, make_silent_callbacks, get_last_consensus
    from chamber.store import save_session

    # Detect encryption
    passphrase = None
    with open(resume_path, "rb") as f:
        head = f.read(64)
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        import getpass
        passphrase = getpass.getpass("Passphrase: ")

    try:
        session = load_session_file(resume_path, passphrase)
    except Exception as e:
        click.echo(f"Failed to load session: {e}", err=True)
        sys.exit(1)

    if extra_document_context:
        if session.document_context:
            session.document_context += "\n\n" + extra_document_context
        else:
            session.document_context = extra_document_context

    from chamber.models import SessionStatus
    session.status = SessionStatus.IDLE
    is_json = output_format == "json"

    if not is_json:
        click.echo(f"Resumed session: {session.topic}")
        click.echo(f"Panel: {', '.join(p.name for p in session.personas)}")
        click.echo(f"Messages: {len(session.messages)}, Last round: {session.current_round}")
        click.echo()

    if one_shot:
        callbacks = make_silent_callbacks() if is_json else make_text_callbacks()

        orchestrator = Orchestrator(
            session=session,
            provider=provider,
            max_rounds=config.rounds,
            depth=config.depth,
            **{k: v for k, v in callbacks.items() if not k.startswith("_")},
        )

        await orchestrator.run()

        save_session(session)

        if is_json:
            print(format_session_json(session, get_last_consensus(callbacks)))
        elif save_path:
            md = export_markdown(session)
            with open(save_path, "w") as f:
                f.write(md)
            print(f"\nSaved to {save_path}", flush=True)
    else:
        from chamber.repl import ChamberREPL, parse_command
        from chamber.output import make_text_callbacks

        repl = ChamberREPL(config=config, provider=provider)
        repl._print_banner()
        repl.session = session

        repl_callbacks = make_text_callbacks(printer=repl._print, token_writer=lambda t: repl._print_token("", t))
        repl.orchestrator = Orchestrator(
            session=session,
            provider=provider,
            max_rounds=config.rounds,
            depth=config.depth,
            **{k: v for k, v in repl_callbacks.items() if not k.startswith("_")},
        )

        repl._print("Session resumed. Use /follow to continue the discussion.\n")

        while True:
            try:
                text = await repl.prompt_session.prompt_async("> ")
                cmd = parse_command(text)
                if await repl._handle_command(cmd):
                    break
            except (KeyboardInterrupt, EOFError):
                break
        repl._print("Session destroyed. Goodbye.")


async def _repl(config, provider, initial_topic, persona_roles, personas_file, document_context, template_name):
    from chamber.repl import ChamberREPL, parse_command
    from chamber.output import make_text_callbacks
    from chamber.store import save_session

    repl = ChamberREPL(config=config, provider=provider)

    if initial_topic:
        repl._print_banner()

        word_limit = get_word_limit(config.depth, 1)
        personas, is_sync = _get_personas(config, provider, initial_topic, persona_roles, personas_file, template_name, word_limit)

        if personas is not None:
            from chamber.session import create_session
            from chamber.orchestrator import Orchestrator

            repl.session = create_session(initial_topic, personas)
            if document_context:
                repl.session.document_context = document_context
            repl._print(f"Panel: {', '.join(p.name for p in personas)}\n")

            repl_callbacks = make_text_callbacks(printer=repl._print, token_writer=lambda t: repl._print_token("", t))
            repl.orchestrator = Orchestrator(
                session=repl.session, provider=provider,
                max_rounds=config.rounds, depth=config.depth,
                **{k: v for k, v in repl_callbacks.items() if not k.startswith("_")},
            )
            await repl.orchestrator.run()
            save_session(repl.session)
        elif persona_roles:
            from chamber.persona import generate_personas_from_roles
            from chamber.session import create_session
            from chamber.orchestrator import Orchestrator
            repl._print("Generating panel from roles...")
            personas = await generate_personas_from_roles(
                roles=list(persona_roles), topic=initial_topic, provider=provider, word_limit=word_limit
            )
            repl.session = create_session(initial_topic, personas)
            if document_context:
                repl.session.document_context = document_context
            repl._print(f"Panel: {', '.join(p.name for p in personas)}\n")

            repl_callbacks = make_text_callbacks(printer=repl._print, token_writer=lambda t: repl._print_token("", t))
            repl.orchestrator = Orchestrator(
                session=repl.session, provider=provider,
                max_rounds=config.rounds, depth=config.depth,
                **{k: v for k, v in repl_callbacks.items() if not k.startswith("_")},
            )
            await repl.orchestrator.run()
            save_session(repl.session)
        else:
            await repl._handle_topic(initial_topic)
            if repl.session and document_context:
                repl.session.document_context = document_context

        while True:
            try:
                text = await repl.prompt_session.prompt_async("> ")
                cmd = parse_command(text)
                if await repl._handle_command(cmd):
                    break
            except (KeyboardInterrupt, EOFError):
                break
        repl._print("Session destroyed. Goodbye.")
    else:
        await repl.run()


def main() -> None:
    """Entry point — dispatch between `chamber share` and the default discussion command."""
    if len(sys.argv) >= 2 and sys.argv[1] == "share":
        from chamber.share import share_command
        share_command.main(args=sys.argv[2:], prog_name="chamber share", standalone_mode=True)
        return
    discuss.main(args=sys.argv[1:], prog_name="chamber", standalone_mode=True)
