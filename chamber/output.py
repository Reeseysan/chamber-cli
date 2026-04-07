"""Output callback factories for Orchestrator.

Eliminates the 6x copy-pasted callback blocks across cli.py and repl.py.
Two modes: text (streaming to terminal) and silent (JSON / scripting).
"""
from __future__ import annotations

import sys
from typing import Callable

from chamber.models import ConsensusResult


def make_text_callbacks(
    printer: Callable[[str], None] = lambda text: print(text, flush=True),
    token_writer: Callable[[str], None] | None = None,
) -> dict:
    """Create orchestrator callbacks for human-readable terminal output.
    
    Args:
        printer: Function to print a line (default: print with flush).
        token_writer: Function to write a single token (default: sys.stdout.write).
    """
    if token_writer is None:
        def token_writer(token: str) -> None:
            sys.stdout.write(token)
            sys.stdout.flush()

    last_consensus: list[ConsensusResult | None] = [None]

    def on_consensus(result: ConsensusResult) -> None:
        last_consensus[0] = result
        printer(f"\n{'═' * 56}")
        if result.reached:
            printer("CONSENSUS REACHED")
        else:
            printer("DISCUSSION ENDED (no full consensus)")
        printer(f"{'═' * 56}")
        printer(result.summary)
        if result.key_points:
            printer("\nKey points:")
            for point in result.key_points:
                printer(f"  - {point}")
        if result.dissenting_views:
            printer("\nDissenting views:")
            for view in result.dissenting_views:
                printer(f"  - {view}")
        printer("")

    callbacks = dict(
        on_token=lambda name, token: token_writer(token),
        on_round_start=lambda r: printer(f"\n{'─' * 2} Round {r} {'─' * 48}\n"),
        on_agent_start=lambda name: printer(f"[{name}]"),
        on_agent_done=lambda name, text: printer(""),
        on_moderator=lambda text: (
            printer(f"{'─' * 2} Moderator {'─' * 45}"),
            printer(text),
            printer(""),
        ),
        on_consensus=on_consensus,
    )
    callbacks["_last_consensus"] = last_consensus
    return callbacks


def make_silent_callbacks() -> dict:
    """Create orchestrator callbacks that capture results without printing.
    
    Used for --format json and MCP server mode.
    """
    last_consensus: list[ConsensusResult | None] = [None]

    callbacks = dict(
        on_consensus=lambda result: last_consensus.__setitem__(0, result),
    )
    callbacks["_last_consensus"] = last_consensus
    return callbacks


def get_last_consensus(callbacks: dict) -> ConsensusResult | None:
    """Extract the last consensus result from a callbacks dict."""
    holder = callbacks.get("_last_consensus")
    if holder and isinstance(holder, list):
        return holder[0]
    return None
