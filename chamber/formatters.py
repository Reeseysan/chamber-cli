from __future__ import annotations

import json
from datetime import timezone

from chamber.models import Session, ConsensusResult


def format_session_json(session: Session, consensus: ConsensusResult | None = None) -> str:
    """Format a completed session as structured JSON for machine consumption."""
    experts = [
        {
            "name": p.name,
            "role": p.role,
            "expertise": p.expertise,
            "avatar_emoji": p.avatar_emoji,
        }
        for p in session.personas
    ]

    # Group messages by round
    rounds: dict[int, dict] = {}
    for msg in session.messages:
        rn = msg.round_number
        if rn not in rounds:
            rounds[rn] = {"number": rn, "contributions": [], "moderator_summary": ""}

        if msg.role == "moderator":
            rounds[rn]["moderator_summary"] = msg.content
        elif msg.role == "user":
            rounds[rn]["contributions"].append({
                "expert": "User",
                "role": "user",
                "content": msg.content,
                "timestamp": msg.timestamp.astimezone(timezone.utc).isoformat(),
            })
        else:
            rounds[rn]["contributions"].append({
                "expert": msg.agent_name,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.astimezone(timezone.utc).isoformat(),
            })

    rounds_list = [rounds[k] for k in sorted(rounds.keys())]

    output = {
        "topic": session.topic,
        "experts": experts,
        "rounds": rounds_list,
        "consensus": None,
    }

    if consensus:
        output["consensus"] = {
            "reached": consensus.reached,
            "summary": consensus.summary,
            "key_points": consensus.key_points,
            "dissenting_views": consensus.dissenting_views,
        }

    return json.dumps(output, indent=2, ensure_ascii=False)
