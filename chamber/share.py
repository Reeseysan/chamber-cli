from __future__ import annotations

import sys

import click
import httpx

from chamber import __version__
from chamber.config import Config
from chamber.models import Session
from chamber.store import latest_session, load_session

try:
    from rich.console import Console
    _console: Console | None = Console()
except ImportError:  # rich is a soft dependency — fall back to click
    _console = None


def build_payload(session: Session) -> dict:
    """Shape a session into the JSON body the Chamber Cloud expects."""
    return {
        "session_id": session.id,
        "topic": session.topic,
        "cli_version": __version__,
        "personas": [
            {
                "name": p.name,
                "role": p.role,
                "expertise": p.expertise,
                "avatar_emoji": p.avatar_emoji,
            }
            for p in session.personas
        ],
        "messages": [
            {
                "agent_name": m.agent_name,
                "role": m.role,
                "content": m.content,
                "round_number": m.round_number,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in session.messages
        ],
        "current_round": session.current_round,
    }


def _print_success(share_url: str) -> None:
    if _console is not None:
        _console.print("[bold green]✅ Session published securely to the cloud![/bold green]")
        _console.print(f"🔗 Share this link with your team: [link={share_url}]{share_url}[/link]")
    else:
        click.secho("✅ Session published securely to the cloud!", fg="green", bold=True)
        click.echo(f"🔗 Share this link with your team: {share_url}")


def _print_error(message: str) -> None:
    if _console is not None:
        _console.print(f"[bold red]Error:[/bold red] {message}")
    else:
        click.secho(f"Error: {message}", fg="red", bold=True, err=True)


def share_session(session: Session, cloud_api_url: str) -> int:
    """POST a session to the cloud and print the share URL. Returns exit code."""
    payload = build_payload(session)
    try:
        resp = httpx.post(cloud_api_url, json=payload, timeout=30)
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        _print_error("Could not reach the Chamber Cloud. Check your connection and try again.")
        return 1
    except httpx.HTTPStatusError as e:
        _print_error(f"Chamber Cloud rejected the upload ({e.response.status_code}).")
        return 1
    except httpx.HTTPError as e:
        _print_error(f"Upload failed: {e}")
        return 1

    try:
        data = resp.json()
    except ValueError:
        _print_error("Chamber Cloud returned an invalid response.")
        return 1

    share_url = data.get("url")
    if not share_url:
        _print_error("Chamber Cloud response did not include a share URL.")
        return 1

    _print_success(share_url)
    return 0


@click.command(name="share")
@click.option(
    "--session-id",
    default=None,
    help="Share a specific session id (default: most recent).",
)
def share_command(session_id: str | None) -> None:
    """Publish your most recent local session to the Chamber Cloud."""
    config = Config.from_env()

    try:
        if session_id:
            session = load_session(session_id)
        else:
            session = latest_session()
            if session is None:
                _print_error(
                    "No local sessions found. Run a discussion first, then try "
                    "`chamber share` again."
                )
                sys.exit(1)
    except FileNotFoundError as e:
        _print_error(str(e))
        sys.exit(1)

    exit_code = share_session(session, config.cloud_api_url)
    sys.exit(exit_code)
