from __future__ import annotations

import json
import os
from pathlib import Path

from chamber.models import Persona
from chamber.persona import build_system_prompt

TEMPLATES_DIR = Path(__file__).parent


def list_templates() -> list[dict]:
    """List all available templates with name and description."""
    templates = []
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            templates.append({
                "name": data["name"],
                "description": data.get("description", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return templates


def load_template(name: str) -> dict:
    """Load a template by name. Returns dict with personas, config_overrides, etc."""
    # Try exact filename first, then slug match
    for f in TEMPLATES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("name") == name:
                return data
        except (json.JSONDecodeError, KeyError):
            continue

    # Try matching by filename stem (e.g., "legal-review" -> "legal_review.json")
    slug = name.replace("-", "_")
    path = TEMPLATES_DIR / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())

    available = [t["name"] for t in list_templates()]
    raise KeyError(
        f"Unknown template: {name!r}. "
        f"Available: {', '.join(available) if available else 'none'}"
    )


def template_to_personas(template: dict, word_limit: int = 200) -> list[Persona]:
    """Convert a template's persona definitions into Persona objects."""
    personas = []
    for entry in template.get("personas", []):
        name = entry["name"]
        role = entry["role"]
        expertise = entry.get("expertise", role)
        avatar = entry.get("avatar_emoji", "\U0001f9d1\u200d\U0001f4bc")
        personas.append(Persona(
            name=name,
            role=role,
            expertise=expertise,
            avatar_emoji=avatar,
            system_prompt=build_system_prompt(name, role, expertise, word_limit),
        ))
    return personas
