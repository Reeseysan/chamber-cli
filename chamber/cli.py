from __future__ import annotations

import sys
import asyncio

import click

from chamber import __version__
from chamber.config import Config


@click.command()
@click.version_option(__version__, prog_name="Chamber CLI")
@click.argument("topic", required=False, default=None)
@click.option("--provider", default=None, help="Provider to use (ollama, lmstudio)")
@click.option("--model", default=None, help="Model name to use")
@click.option("--agents", default=None, type=int, help="Number of expert agents (default: 3, max: 5)")
@click.option("--rounds", default=None, type=int, help="Max discussion rounds (default: 3, max: 5)")
@click.option("--one-shot", is_flag=True, help="Run discussion and exit (no REPL)")
@click.option("--proxy", default=None, help="SOCKS5 proxy URL for remote providers")
@click.option("--save", "save_path", default=None, help="Save export to file after discussion")
def main(topic, provider, model, agents, rounds, one_shot, proxy, save_path):
    """Chamber CLI — Private expert panels in your terminal."""
    config = Config.from_env(
        provider=provider,
        model=model,
        agents=min(agents, 5) if agents else None,
        rounds=min(rounds, 5) if rounds else None,
        proxy=proxy,
    )

    # Import providers to trigger registration
    import chamber.providers.ollama  # noqa: F401
    import chamber.providers.lmstudio  # noqa: F401
    from chamber.providers import get_provider

    llm = None
    explicit_provider = provider is not None

    if explicit_provider:
        # User explicitly chose a provider
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
        # Auto-discover: try Ollama first, then LM Studio
        import httpx

        for name, url in [("ollama", config.ollama_url), ("lmstudio", config.lmstudio_url)]:
            check_url = f"{url}/" if name == "ollama" else f"{url}/v1/models"
            try:
                resp = httpx.get(check_url, timeout=3)
                kwargs = {"base_url": url}
                if config.model:
                    kwargs["model"] = config.model
                llm = get_provider(name, **kwargs)
                config.provider = name
                break
            except (httpx.ConnectError, httpx.TimeoutException):
                continue

        if llm is None:
            click.echo(
                "No local model server detected.\n"
                f"  Ollama:    not running at {config.ollama_url}\n"
                f"  LM Studio: not running at {config.lmstudio_url}\n\n"
                "Install Ollama: https://ollama.com\n"
                "Or start LM Studio's local server.",
                err=True,
            )
            sys.exit(1)

    if one_shot:
        if not topic:
            click.echo("No topic provided. Usage: chamber \"your topic\" --one-shot", err=True)
            sys.exit(1)
        asyncio.run(_one_shot(config, llm, topic, save_path))
    else:
        asyncio.run(_repl(config, llm, topic))


async def _one_shot(config, provider, topic, save_path):
    from chamber.persona import generate_personas
    from chamber.session import create_session
    from chamber.orchestrator import Orchestrator
    from chamber.export import export_markdown

    print("Generating panel...", flush=True)
    personas = await generate_personas(topic, provider, count=config.agents)
    session = create_session(topic, personas)

    panel_names = ", ".join(p.name for p in personas)
    print(f"Panel: {panel_names}\n", flush=True)

    def on_token(name, token):
        sys.stdout.write(token)
        sys.stdout.flush()

    orchestrator = Orchestrator(
        session=session,
        provider=provider,
        max_rounds=config.rounds,
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


async def _repl(config, provider, initial_topic):
    from chamber.repl import ChamberREPL, parse_command

    repl = ChamberREPL(config=config, provider=provider)
    if initial_topic:
        repl._print_banner()
        await repl._handle_topic(initial_topic)
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
