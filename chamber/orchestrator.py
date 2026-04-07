from __future__ import annotations

import random
import sys
from typing import Callable, Awaitable

from chamber.models import Session, SessionStatus, Message, ConsensusResult
from chamber.config import get_word_limit, get_summary_limit
from chamber.expert import ExpertAgent
from chamber.moderator import ModeratorAgent
from chamber.persona import build_system_prompt
from chamber.providers.base import LLMProvider

# Approximate token-to-word ratio (1 token ≈ 0.75 words)
_WORDS_PER_TOKEN = 0.75

# Default context budget in words — conservative for small local models
_DEFAULT_CONTEXT_BUDGET_WORDS = 6000  # ~8K tokens, safe for most 7B/8B models

# How many recent rounds to always keep in full
_MIN_RECENT_ROUNDS = 2


def _estimate_words(messages: list[Message]) -> int:
    """Estimate total word count across messages."""
    return sum(len(m.content.split()) for m in messages)


def _truncate_history(
    messages: list[Message],
    current_round: int,
    context_budget_words: int = _DEFAULT_CONTEXT_BUDGET_WORDS,
) -> list[Message]:
    """Truncate message history to fit within a context budget.
    
    Strategy:
    - Always keep all messages from the most recent N rounds in full
    - For older rounds, keep only moderator summaries (they compress expert positions)
    - This preserves recent debate context while staying within budget
    
    Returns a (potentially shorter) list of messages.
    """
    if not messages:
        return messages

    total_words = _estimate_words(messages)
    if total_words <= context_budget_words:
        return messages  # Fits fine, no truncation needed

    # Split into recent and older messages
    recent_cutoff = max(1, current_round - _MIN_RECENT_ROUNDS + 1)

    recent = [m for m in messages if m.round_number >= recent_cutoff]
    older = [m for m in messages if m.round_number < recent_cutoff]

    if not older:
        return messages  # Only recent rounds, can't compress further

    # Keep only moderator summaries from older rounds (they compress the round)
    compressed_older = [m for m in older if m.role == "moderator"]

    # Add a system note about truncation if we dropped messages
    dropped_count = len(older) - len(compressed_older)
    if dropped_count > 0:
        first_round = min(m.round_number for m in older) if older else 1
        last_round = max(m.round_number for m in older) if older else 1
        note = Message(
            session_id=messages[0].session_id if messages else "",
            agent_name="System",
            role="system",
            content=f"[Earlier rounds {first_round}–{last_round} summarized by moderator. {dropped_count} individual responses omitted for context budget.]",
            round_number=first_round,
        )
        result = [note] + compressed_older + recent
    else:
        result = compressed_older + recent

    return result


class Orchestrator:
    def __init__(
        self,
        session: Session,
        provider: LLMProvider,
        max_rounds: int = 3,
        depth: str = "standard",
        context_budget_words: int = _DEFAULT_CONTEXT_BUDGET_WORDS,
        on_token: Callable[[str, str], None] | None = None,
        on_round_start: Callable[[int], None] | None = None,
        on_agent_start: Callable[[str], None] | None = None,
        on_agent_done: Callable[[str, str], None] | None = None,
        on_moderator: Callable[[str], None] | None = None,
        on_consensus: Callable[[ConsensusResult], None] | None = None,
    ):
        self.session = session
        self.provider = provider
        self.max_rounds = max_rounds
        self.depth = depth
        self.context_budget_words = context_budget_words
        self._on_token = on_token or (lambda name, token: None)
        self._on_round_start = on_round_start or (lambda r: None)
        self._on_agent_start = on_agent_start or (lambda name: None)
        self._on_agent_done = on_agent_done or (lambda name, text: None)
        self._on_moderator = on_moderator or (lambda text: None)
        self._on_consensus = on_consensus or (lambda result: None)
        self._pending_user_messages: list[str] = []

        self.experts = [
            ExpertAgent(persona=p, provider=provider)
            for p in session.personas
        ]
        self.moderator = ModeratorAgent(provider=provider)

    def inject_user_message(self, content: str) -> None:
        """Queue a user follow-up to be injected before the next round."""
        self._pending_user_messages.append(content)

    def _update_persona_word_limits(self, round_num: int) -> None:
        """Update each expert's system prompt with the round-appropriate word limit."""
        word_limit = get_word_limit(self.depth, round_num)
        for expert in self.experts:
            p = expert.persona
            expert.persona = p.model_copy(update={
                "system_prompt": build_system_prompt(p.name, p.role, p.expertise, word_limit)
            })

    def _get_history_for_llm(self) -> list[Message]:
        """Get context-budgeted history for LLM calls."""
        return _truncate_history(
            self.session.messages,
            self.session.current_round,
            self.context_budget_words,
        )

    async def run(self) -> None:
        session = self.session
        session.status = SessionStatus.DISCUSSING
        doc_context = session.document_context

        for round_num in range(1, self.max_rounds + 1):
            session.current_round = round_num
            self._on_round_start(round_num)

            # Update word limits for this round
            self._update_persona_word_limits(round_num)

            # Inject any pending user messages
            for content in self._pending_user_messages:
                msg = Message(
                    session_id=session.id,
                    agent_name="User",
                    role="user",
                    content=content,
                    round_number=round_num,
                )
                session.messages.append(msg)
            self._pending_user_messages.clear()

            # Shuffle expert order each round
            order = list(range(len(self.experts)))
            random.shuffle(order)

            for idx in order:
                expert = self.experts[idx]
                agent_name = expert.persona.name
                self._on_agent_start(agent_name)

                async def on_token(token: str, _name=agent_name) -> None:
                    self._on_token(_name, token)

                # Use budgeted history instead of full history
                budgeted_history = self._get_history_for_llm()

                full_text = await expert.take_turn(
                    history=budgeted_history,
                    round_number=round_num,
                    on_token=on_token,
                    document_context=doc_context,
                )

                msg = Message(
                    session_id=session.id,
                    agent_name=agent_name,
                    role="expert",
                    content=full_text,
                    round_number=round_num,
                )
                session.messages.append(msg)
                self._on_agent_done(agent_name, full_text)

            # Moderator summary
            summary_limit = get_summary_limit(self.depth)
            budgeted_history = self._get_history_for_llm()
            summary = await self.moderator.summarize_round(
                history=budgeted_history,
                round_number=round_num,
                summary_limit=summary_limit,
                document_context=doc_context,
            )
            mod_msg = Message(
                session_id=session.id,
                agent_name="Moderator",
                role="moderator",
                content=summary,
                round_number=round_num,
            )
            session.messages.append(mod_msg)
            self._on_moderator(summary)

            # Consensus check
            consensus = await self.moderator.check_consensus(
                history=budgeted_history,
                round_number=round_num,
                max_rounds=self.max_rounds,
                depth=self.depth,
                document_context=doc_context,
            )

            if consensus.reached:
                session.status = SessionStatus.CONSENSUS
                self._on_consensus(consensus)
                break

        # Final consensus if max rounds exhausted
        if session.status != SessionStatus.CONSENSUS:
            budgeted_history = self._get_history_for_llm()
            final = await self.moderator.check_consensus(
                history=budgeted_history,
                round_number=self.max_rounds,
                max_rounds=self.max_rounds,
                depth=self.depth,
                document_context=doc_context,
            )
            self._on_consensus(final)

        session.status = SessionStatus.ENDED
