from __future__ import annotations

import json

from chamber.models import Message, ConsensusResult
from chamber.providers.base import LLMProvider

MODERATOR_SYSTEM = """You are the moderator of an expert panel discussion.
Your job is to:
1. Summarize each round's key points of agreement and disagreement
2. Detect when consensus is forming
3. Keep the discussion productive

Be concise. Under 150 words for summaries."""

CONSENSUS_PROMPT = """You are analyzing an expert panel discussion for consensus.
Evaluate whether the experts have reached broad agreement on the core question.

You MUST respond with ONLY valid JSON in this exact format:
{
  "reached": true or false,
  "summary": "2-3 paragraph plain summary of what experts agreed on and one clear recommendation",
  "key_points": ["point 1", "point 2"],
  "dissenting_views": ["dissent 1"]
}"""


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()
    return text


def _format_history(history: list[Message]) -> str:
    lines = []
    for msg in history:
        lines.append(f"[{msg.agent_name}]: {msg.content}")
    return "\n\n".join(lines)


class ModeratorAgent:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def summarize_round(
        self,
        history: list[Message],
        round_number: int,
    ) -> str:
        formatted = _format_history(history)
        return await self.provider.completion(
            system=MODERATOR_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize round {round_number} of the discussion:\n\n{formatted}",
                }
            ],
        )

    async def check_consensus(
        self,
        history: list[Message],
        round_number: int,
        max_rounds: int,
    ) -> ConsensusResult:
        formatted = _format_history(history)

        urgency = ""
        if round_number >= max_rounds - 1:
            urgency = " This is one of the final rounds — lean toward declaring consensus if positions are close."

        raw = await self.provider.json_completion(
            system=CONSENSUS_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Round {round_number}/{max_rounds}.{urgency}\n\n"
                        f"Discussion so far:\n\n{formatted}"
                    ),
                }
            ],
        )

        raw = _strip_markdown_fences(raw)

        try:
            data = json.loads(raw)
            return ConsensusResult(**data)
        except (json.JSONDecodeError, ValueError):
            return ConsensusResult(
                reached=False,
                summary="Unable to determine consensus at this time.",
            )
