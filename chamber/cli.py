from __future__ import annotations

import sys
import asyncio

import click

from chamber import __version__
from chamber.config import Config, get_word_limit


@click.command()
@click.version_option(__version__, prog_name="Chamber CLI")
@click.argument("topic", required=False, default=None)
@click.option("--provider", default=None, help="Provider to use (ollama, lmstudio)")
@click.option("--model", default=None, help="Model name to use")
@click.option("--agents", default=None, type=int, help="Number of expert agents (default: 3, max: 5)")
@click.option("--rounds", default=None, type=int, help="Max discussion rounds (default: 3, max: 5)")
@click.option("--depth", default=None, type=click.Choice(["brief", "standard", "deep"]), help="Discussion depth (default: standard)")
@click.option("--one-shot", is_flag=True, help="Run discussion and exit (no REPL)")
@click.option("--proxy", default=None, help="SOCKS5 proxy URL for remote providers")
@click.option("--save", "save_path", default=None, help="Save export to file after discussion")
@click.option("--persona", "persona_roles", multiple=True, help="Expert role (repeatable)")
@click.option("--personas", "personas_file", default=None, help="Path to personas JSON file")
@click.option("--doc", "doc_paths", multiple=True, help="Document file to load (repeatable)")
def main(topic, provider, model, agents, rounds, depth, one_shot, proxy, save_path, persona_roles, personas_file, doc_paths):
    """Chamber CLI — Private expert panels in your terminal."""
    if persona_roles and personas_file:
        click.echo("Cannot use both --persona and --personas. Pick one.", err=True)
        sys.exit(1)

    config = Config.from_env(
        provider=provider,
        model=model,
        agents=min(agents, 5) if agents else None,
        rounds=min(rounds, 5) if rounds else None,
        depth=depth,
        proxy=proxy,
    )

    # Import providers to trigger registration
    import chamber.providers.ollama  # noqa: F401
    import chamber.providers.lmstudio  # noqa: F401
    from chamber.providers import get_provider

    llm = None
    explicit_provider = provider is not None

    if explicit_provider:
        kwargs = {"model": config.model} if config.model else {}
        if config.provider == "ollama":
            kwargs["base_url"] = config.ollama_url
        elif config.provider == "lmstudio":
            kwargs["base_url"] = config.lmstudio_url
        try:
            llm = get_provider(config.provider, **kwargs)
        except KeyError:
            click.echo(f"Unknown provider: {config.provider}", err=True)
            sys.exit(1)
    else:
        import httpx
        for name, url in [("ollama", config.ollama_url), ("lmstudio", config.lmstudio_url)]:
            check_url = f"{url}/" if name == "ollama" else f"{url}/v1/models"
            try:
                resp = httpx.get(check_url, timeout=3)
                kwargs = {"base_url": url}
                if config.model:
                    kwargs["model"] = config.model
                elif name == "lmstudio":
                    # Auto-detect loaded model from LM Studio
                    try:
                        models = resp.json().get("data", [])
                        if models:
                            kwargs["model"] = models[0].get("id", "local-model")
                    except Exception:
                        pass
                llm = get_provider(name, **kwargs)
                config.provider = name
                # Update config.model so banner shows the real model
                config.model = getattr(llm, "model", config.model)
                break
            except (httpx.ConnectError, httpx.TimeoutException):
                continue

        if llm is None:
            click.echo(
                "No local model server detected.\n"
                f"  Ollama:    not running at {config.ollama_url}\n"
                f"  LM Studio: not running at {config.lmstudio_url}\n\n"
                "Install Ollama: https://ollama.com\n"
                "Or start LM Studio's local server in Developer tab.",
                err=True,
            )
            sys.exit(1)

    # Load documents
    document_context = ""
    if doc_paths:
        from chamber.document import load_document, DocumentError
        parts = []
        for path in doc_paths:
            try:
                parts.append(load_document(path))
            except DocumentError as e:
                click.echo(f"Error loading {path}: {e}", err=True)
                sys.exit(1)
        document_context = "\n\n".join(parts)

    # Check stdin for piped content
    if not sys.stdin.isatty():
        from chamber.document import load_from_stdin, DocumentError
        try:
            stdin_doc = load_from_stdin(sys.stdin)
            if document_context:
                document_context += "\n\n" + stdin_doc
            else:
                document_context = stdin_doc
        except DocumentError:
            pass  # Empty stdin is fine

    if one_shot:
        if not topic:
            click.echo("No topic provided. Usage: chamber \"your topic\" --one-shot", err=True)
            sys.exit(1)
        asyncio.run(_one_shot(config, llm, topic, save_path, persona_roles, personas_file, document_context))
    else:
        asyncio.run(_repl(config, llm, topic, persona_roles, personas_file, document_context))


async def _one_shot(config, provider, topic, save_path, persona_roles, personas_file, document_context):
    from chamber.persona import generate_personas, generate_personas_from_roles, load_personas_from_file
    from chamber.session import create_session
    from chamber.orchestrator import Orchestrator
    from chamber.export import export_markdown

    word_limit = get_word_limit(config.depth, 1)

    if personas_file:
        personas = load_personas_from_file(personas_file)
    elif persona_roles:
        print("Generating panel from roles...", flush=True)
        personas = await generate_personas_from_roles(
            roles=list(persona_roles), topic=topic, provider=provider, word_limit=word_limit
        )
    else:
        print("Generating panel...", flush=True)
        personas = await generate_personas(topic, provider, count=config.agents, word_limit=word_limit)

    session = create_session(topic, personas)
    session.document_context = document_context

    panel_names = ", ".join(p.name for p in personas)
    print(f"Panel: {panel_names}\n", flush=True)

    def on_token(name, token):
        sys.stdout.write(token)
        sys.stdout.flush()

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=config.rounds,
        depth=config.depth,
        on_token=on_token,
        on_round_start=lambda r: print(f"\n{'─' * 2} Round {r} {'─' * 48}\n"),
        on_agent_start=lambda name: print(f"[{name}]"),
        on_agent_done=lambda name, text: print(),
        on_moderator=lambda text: print(f"{'─' * 2} Moderator {'─' * 45}\n{text}\n"),
        on_consensus=lambda result: print(f"\n{'═' * 56}\n{result.summary}\n"),
    )

    await orchestrator.run()

    if save_path:
        md = export_markdown(session)
        with open(save_path, "w") as f:
            f.write(md)
        print(f"\nSaved to {save_path}", flush=True)


async def _repl(config, provider, initial_topic, persona_roles, personas_file, document_context):
    from chamber.repl import ChamberREPL, parse_command

    repl = ChamberREPL(config=config, provider=provider)

    if initial_topic:
        repl._print_banner()

        if personas_file:
            from chamber.persona import load_personas_from_file
            from chamber.session import create_session
            from chamber.orchestrator import Orchestrator
            personas = load_personas_from_file(personas_file)
            repl.session = create_session(initial_topic, personas)
            if document_context:
                repl.session.document_context = document_context
            panel_names = ", ".join(p.name for p in personas)
            repl._print(f"Panel: {panel_names}\n")
            repl.orchestrator = Orchestrator(
                session=repl.session, provider=provider,
                max_rounds=config.rounds, depth=config.depth,
                on_token=repl._print_token,
                on_round_start=lambda r: repl._print(f"\n{'─' * 2} Round {r} {'─' * 48}\n"),
                on_agent_start=lambda name: repl._print(f"[{name}]"),
                on_agent_done=lambda name, text: repl._print("\n"),
                on_moderator=lambda text: (repl._print(f"{'─' * 2} Moderator {'─' * 45}"), repl._print(text), repl._print()),
                on_consensus=lambda result: repl._print_consensus(result),
            )
            await repl.orchestrator.run()
        elif persona_roles:
            from chamber.persona import generate_personas_from_roles
            from chamber.session import create_session
            from chamber.orchestrator import Orchestrator
            word_limit = get_word_limit(config.depth, 1)
            repl._print("Generating panel from roles...")
            personas = await generate_personas_from_roles(
                roles=list(persona_roles), topic=initial_topic, provider=provider, word_limit=word_limit
            )
            repl.session = create_session(initial_topic, personas)
            if document_context:
                repl.session.document_context = document_context
            panel_names = ", ".join(p.name for p in personas)
            repl._print(f"Panel: {panel_names}\n")
            repl.orchestrator = Orchestrator(
                session=repl.session, provider=provider,
                max_rounds=config.rounds, depth=config.depth,
                on_token=repl._print_token,
                on_round_start=lambda r: repl._print(f"\n{'─' * 2} Round {r} {'─' * 48}\n"),
                on_agent_start=lambda name: repl._print(f"[{name}]"),
                on_agent_done=lambda name, text: repl._print("\n"),
                on_moderator=lambda text: (repl._print(f"{'─' * 2} Moderator {'─' * 45}"), repl._print(text), repl._print()),
                on_consensus=lambda result: repl._print_consensus(result),
            )
            await repl.orchestrator.run()
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
