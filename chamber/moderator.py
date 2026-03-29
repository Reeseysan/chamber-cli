from __future__ import annotations

import json

from chamber.models import Message, ConsensusResult
from chamber.providers.base import LLMProvider

MODERATOR_SYSTEM = """You are the moderator of an expert panel discussion.
Your job is to:
1. Summarize each round's key points of agreement and disagreement
2. Detect when consensus is forming
3. Keep the discussion productive

Be concise. Under {word_limit} words for summaries."""

CONSENSUS_BRIEF = """You are analyzing an expert panel discussion for consensus.
Evaluate whether the experts have reached broad agreement on the core question.
Be concise and brief.

You MUST respond with ONLY valid JSON in this exact format:
{{
  "reached": true or false,
  "summary": "1-2 sentence summary of what experts agreed on and one clear recommendation",
  "key_points": ["point 1", "point 2"],
  "dissenting_views": ["dissent 1"]
}}"""

CONSENSUS_STANDARD = """You are analyzing an expert panel discussion for consensus.
Evaluate whether the experts have reached broad agreement on the core question.
Produce a structured verdict.

You MUST respond with ONLY valid JSON in this exact format:
{{
  "reached": true or false,
  "summary": "VERDICT: [one sentence decision]\\n\\nEXPERT POSITIONS:\\n[For each expert: name, stance, confidence high/medium/low]\\n\\nKEY ARGUMENTS:\\n[2-3 decisive points]\\n\\nDISSENTING VIEW:\\n[minority position and why it didn't prevail]\\n\\nRECOMMENDATION:\\n[clear actionable next step]",
  "key_points": ["point 1", "point 2"],
  "dissenting_views": ["dissent 1"]
}}"""

CONSENSUS_DEEP = """You are a senior analyst synthesizing an expert panel discussion into a structured verdict.
This should read like a consultant's executive brief — precise, actionable, authoritative.

You MUST respond with ONLY valid JSON in this exact format:
{{
  "reached": true or false,
  "summary": "VERDICT: [one sentence decision]\\n\\nEXPERT POSITIONS:\\n[For each expert: name, stance, confidence 1-10, reasoning summary]\\n\\nKEY ARGUMENTS THAT SHAPED THE OUTCOME:\\n[2-3 decisive reasoning points with detail]\\n\\nDISSENTING VIEW:\\n[what the minority argued and why it didn't prevail]\\n\\nRECOMMENDATION:\\n[clear actionable recommendation with reasoning]\\n\\nRISK FACTORS:\\n[what could change this conclusion]\\n\\nNEXT STEPS:\\n1. [concrete action]\\n2. [concrete action]\\n3. [concrete action]",
  "key_points": ["point 1", "point 2", "point 3"],
  "dissenting_views": ["dissent with reasoning"]
}}

Make the verdict thorough and structured. The quality gap between this and a basic summary should be immediately obvious."""

CONSENSUS_PROMPTS = {
    "brief": CONSENSUS_BRIEF,
    "standard": CONSENSUS_STANDARD,
    "deep": CONSENSUS_DEEP,
}


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
        summary_limit: int = 200,
        document_context: str = "",
    ) -> str:
        formatted = _format_history(history)
        system = MODERATOR_SYSTEM.format(word_limit=summary_limit)
        if document_context:
            system += f"\n\nReference documents:\n{document_context}"
        return await self.provider.completion(
            system=system,
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
        depth: str = "standard",
        document_context: str = "",
    ) -> ConsensusResult:
        formatted = _format_history(history)

        urgency = ""
        if round_number >= max_rounds - 1:
            urgency = " This is one of the final rounds — lean toward declaring consensus if positions are close."

        system = CONSENSUS_PROMPTS.get(depth, CONSENSUS_STANDARD)
        if document_context:
            system += f"\n\nReference documents:\n{document_context}"

        raw = await self.provider.json_completion(
            system=system,
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
