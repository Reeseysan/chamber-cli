from __future__ import annotations

import re
import uuid

from chamber.models import Session, SessionStatus, Persona, Message, ConsensusResult
from chamber.persona import build_system_prompt
from chamber.export import decrypt_export

EXPORT_HEADER = "<!-- chamber-export-v1 -->"


def _is_encrypted(data: bytes) -> bool:
    """Check if data looks like an encrypted export (binary, not valid UTF-8 markdown)."""
    try:
        text = data.decode("utf-8")
        # If it decodes as UTF-8 and looks like markdown, it's plaintext
        return not (text.startswith("#") or text.startswith("<!--") or text.startswith("\n"))
    except UnicodeDecodeError:
        return True


def _parse_panel(text: str) -> list[Persona]:
    """Parse the ## Panel section into Persona objects."""
    personas = []
    # Match: - **Name** — Role (Expertise)
    pattern = re.compile(r"- \*\*(.+?)\*\* — (.+?) \((.+?)\)")
    for match in pattern.finditer(text):
        name, role, expertise = match.groups()
        personas.append(Persona(
            name=name,
            role=role,
            expertise=expertise,
            avatar_emoji="\U0001f9d1\u200d\U0001f4bc",
            system_prompt=build_system_prompt(name, role, expertise),
        ))
    return personas


def _parse_messages(text: str, session_id: str) -> list[Message]:
    """Parse round/message blocks from markdown export."""
    messages = []
    current_round = 0

    lines = text.split("\n")
    i = 0
    current_agent = ""
    current_role = ""
    content_lines: list[str] = []

    def flush():
        nonlocal current_agent, current_role, content_lines
        if current_agent and content_lines:
            content = "\n".join(content_lines).strip()
            if content:
                messages.append(Message(
                    session_id=session_id,
                    agent_name=current_agent,
                    role=current_role,
                    content=content,
                    round_number=current_round,
                ))
        current_agent = ""
        current_role = ""
        content_lines = []

    while i < len(lines):
        line = lines[i]

        # Round header
        round_match = re.match(r"^## Round (\d+)", line)
        if round_match:
            flush()
            current_round = int(round_match.group(1))
            i += 1
            continue

        # Agent header: ### [AgentName] or ### Moderator or ### You
        agent_match = re.match(r"^### \[(.+?)\]$", line)
        if agent_match:
            flush()
            current_agent = agent_match.group(1)
            current_role = "expert"
            i += 1
            continue

        if line.strip() == "### Moderator":
            flush()
            current_agent = "Moderator"
            current_role = "moderator"
            i += 1
            continue

        if line.strip() == "### You":
            flush()
            current_agent = "User"
            current_role = "user"
            i += 1
            continue

        # Skip panel section
        if line.startswith("## Panel"):
            flush()
            # Skip until next ## section
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue

        # Content line
        if current_agent:
            content_lines.append(line)

        i += 1

    flush()
    return messages


def parse_exported_markdown(text: str) -> Session:
    """Reconstruct a Session from exported markdown.
    
    Parses the standard export format:
      # Chamber Discussion: <topic>
      ## Panel
      - **Name** — Role (Expertise)
      ## Round 1
      ### [AgentName]
      content...
    """
    # Strip export header if present
    text = text.replace(EXPORT_HEADER, "").strip()

    # Extract topic
    topic_match = re.match(r"# Chamber Discussion: (.+)", text)
    topic = topic_match.group(1).strip() if topic_match else "Resumed session"

    # Extract panel
    panel_match = re.search(r"## Panel\n((?:- .+\n)+)", text)
    personas = _parse_panel(panel_match.group(1)) if panel_match else []

    session_id = str(uuid.uuid4())

    # Extract messages
    messages = _parse_messages(text, session_id)

    # Determine round number
    max_round = max((m.round_number for m in messages), default=0)

    return Session(
        id=session_id,
        topic=topic,
        personas=personas,
        messages=messages,
        current_round=max_round,
        status=SessionStatus.ENDED,
    )


def load_session_file(path: str, passphrase: str | None = None) -> Session:
    """Load a session from an exported file (plaintext or encrypted).
    
    Args:
        path: Path to the export file.
        passphrase: Passphrase for encrypted exports (prompted if needed but not provided).
    
    Returns:
        Reconstructed Session object.
    """
    with open(path, "rb") as f:
        data = f.read()

    if _is_encrypted(data):
        if passphrase is None:
            raise ValueError("File appears encrypted but no passphrase provided. Use --resume with interactive mode.")
        markdown = decrypt_export(data, passphrase)
    else:
        markdown = data.decode("utf-8")

    return parse_exported_markdown(markdown)
