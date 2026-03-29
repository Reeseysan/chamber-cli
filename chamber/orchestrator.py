from __future__ import annotations

import random
from typing import Callable, Awaitable

from chamber.models import Session, Message, ConsensusResult
from chamber.expert import ExpertAgent
from chamber.moderator import ModeratorAgent
from chamber.providers.base import LLMProvider


class Orchestrator:
    def __init__(
        self,
        session: Session,
        provider: LLMProvider,
        max_rounds: int = 3,
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
        self._on_token = on_token or (lambda name, token: None)
        self._on_round_start = on_round_start or (lambda r: None)
        self._on_agent_start = on_agent_start or (lambda name: None)
        self._on_agent_done = on_agent_done or (lambda name, text: None)
        self._on_moderator = on_moderator or (lambda text: None)
        self._on_consensus = on_consensus or (lambda result: None)
        self._pending_user_messages: list[str] = []

        # Build agents — all use the same provider in CLI (single local model)
        self.experts = [
            ExpertAgent(persona=p, provider=provider)
            for p in session.personas
        ]
        self.moderator = ModeratorAgent(provider=provider)

    def inject_user_message(self, content: str) -> None:
        """Queue a user follow-up to be injected before the next round."""
        self._pending_user_messages.append(content)

    async def run(self) -> None:
        session = self.session
        session.status = "discussing"

        for round_num in range(1, self.max_rounds + 1):
            session.current_round = round_num
            self._on_round_start(round_num)

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

                full_text = await expert.take_turn(
                    history=session.messages,
                    round_number=round_num,
                    on_token=on_token,
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
            summary = await self.moderator.summarize_round(
                history=session.messages,
                round_number=round_num,
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
                history=session.messages,
                round_number=round_num,
                max_rounds=self.max_rounds,
            )

            if consensus.reached:
                session.status = "consensus"
                self._on_consensus(consensus)
                break

        # Final consensus if max rounds exhausted
        if session.status != "consensus":
            final = await self.moderator.check_consensus(
                history=session.messages,
                round_number=self.max_rounds,
                max_rounds=self.max_rounds,
            )
            self._on_consensus(final)

        session.status = "ended"
