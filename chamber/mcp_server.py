"""Chamber CLI MCP Server Mode.

Exposes Chamber as an MCP (Model Context Protocol) server so any
MCP-compatible client (Claude Code, Cursor, etc.) can invoke
multi-agent discussion panels.

Requires: pip install chamber-cli[mcp]
"""
from __future__ import annotations

import asyncio
import json


def create_mcp_server():
    """Create and configure the MCP server with Chamber tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP server mode requires the mcp package.\n"
            "Install it with: pip install chamber-cli[mcp]"
        )

    mcp = FastMCP("chamber-cli")

    @mcp.tool()
    async def discuss(
        topic: str,
        template: str | None = None,
        agents: int = 3,
        rounds: int = 3,
        depth: str = "standard",
        provider_name: str | None = None,
        model: str | None = None,
    ) -> str:
        """Run a multi-agent expert panel discussion on a topic.
        
        Args:
            topic: The topic to discuss.
            template: Optional template name (e.g., 'code-review', 'legal-review', 'threat-model').
            agents: Number of expert agents (1-5, default 3).
            rounds: Max discussion rounds (1-5, default 3).
            depth: Discussion depth — 'brief', 'standard', or 'deep'.
            provider_name: LLM provider to use (will auto-detect if not specified).
            model: Model name to use.
        
        Returns:
            JSON string with the full discussion results.
        """
        from chamber.config import Config, get_word_limit
        from chamber.session import create_session
        from chamber.orchestrator import Orchestrator
        from chamber.formatters import format_session_json
        from chamber.models import ConsensusResult

        config = Config.from_env(
            provider=provider_name,
            model=model,
            agents=min(max(agents, 1), 5),
            rounds=min(max(rounds, 1), 5),
            depth=depth,
        )

        # Set up provider
        llm = _get_provider_for_mcp(config)

        # Get personas
        if template:
            from chamber.templates import load_template, template_to_personas
            tmpl = load_template(template)
            word_limit = get_word_limit(config.depth, 1)
            personas = template_to_personas(tmpl, word_limit)
            # Apply template config overrides
            overrides = tmpl.get("config_overrides", {})
            if "depth" in overrides and depth == "standard":
                config.depth = overrides["depth"]
            if "rounds" in overrides and rounds == 3:
                config.rounds = overrides["rounds"]
        else:
            from chamber.persona import generate_personas
            word_limit = get_word_limit(config.depth, 1)
            personas = await generate_personas(topic, llm, count=config.agents, word_limit=word_limit)

        session = create_session(topic, personas)
        last_consensus = [None]

        orchestrator = Orchestrator(
            session=session,
            provider=llm,
            max_rounds=config.rounds,
            depth=config.depth,
            on_consensus=lambda result: last_consensus.__setitem__(0, result),
        )

        await orchestrator.run()

        return format_session_json(session, last_consensus[0])

    @mcp.tool()
    async def list_available_templates() -> str:
        """List all available discussion templates.
        
        Returns:
            JSON array of templates with name and description.
        """
        from chamber.templates import list_templates
        return json.dumps(list_templates(), indent=2)

    @mcp.resource("chamber://status")
    async def get_status() -> str:
        """Get current Chamber CLI status and configuration."""
        from chamber import __version__
        from chamber.providers import discover_providers
        return json.dumps({
            "version": __version__,
            "registered_providers": discover_providers(),
        }, indent=2)

    return mcp


def _get_provider_for_mcp(config):
    """Resolve provider for MCP mode (same logic as CLI but non-interactive)."""
    import httpx
    from chamber.providers import get_provider

    # Import all providers to trigger registration
    import chamber.providers.ollama  # noqa: F401
    import chamber.providers.lmstudio  # noqa: F401

    # Try importing remote providers (may fail if keys not set, that's ok)
    _try_import("chamber.providers.openai")
    _try_import("chamber.providers.anthropic")
    _try_import("chamber.providers.openrouter")

    if config.provider != "ollama":
        # Explicit provider requested
        kwargs = {}
        if config.model:
            kwargs["model"] = config.model
        if config.provider == "ollama":
            kwargs["base_url"] = config.ollama_url
        elif config.provider == "lmstudio":
            kwargs["base_url"] = config.lmstudio_url
        return get_provider(config.provider, **kwargs)

    # Auto-detect
    for name, url in [("ollama", config.ollama_url), ("lmstudio", config.lmstudio_url)]:
        check_url = f"{url}/" if name == "ollama" else f"{url}/v1/models"
        try:
            resp = httpx.get(check_url, timeout=3)
            kwargs = {"base_url": url}
            if config.model:
                kwargs["model"] = config.model
            llm = get_provider(name, **kwargs)
            config.provider = name
            config.model = getattr(llm, "model", config.model)
            return llm
        except (httpx.ConnectError, httpx.TimeoutException):
            continue

    raise RuntimeError(
        "No LLM provider available. Start Ollama/LM Studio or set API keys for remote providers."
    )


def _try_import(module: str):
    """Try to import a module, silently ignore failures."""
    try:
        __import__(module)
    except (ImportError, ValueError):
        pass


def run_mcp_server():
    """Entry point for MCP server mode."""
    mcp = create_mcp_server()
    mcp.run()
