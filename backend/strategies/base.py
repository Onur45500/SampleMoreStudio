"""Strategy base interface — shared by Phase 1 and Phase 2."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Literal

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import ANSWER_INSTRUCTION
from backend.token_budget import BudgetTracker
from backend.types import StrategyResult, Task, Turn


class Strategy(ABC):
    name: str
    phase: Literal["phase1_reasoning", "phase2_agent"]

    @abstractmethod
    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        """Spend as close to token_budget completion tokens as possible without exceeding it."""

    def _system_prompt(self, task: Task) -> str:
        return (
            "You are a careful problem-solving assistant. "
            + ANSWER_INSTRUCTION
        )

    def _user_prompt(self, task: Task) -> str:
        return task.prompt.strip() + "\n\n" + ANSWER_INSTRUCTION

    def _make_turn(
        self,
        role: str,
        content: str,
        tokens: int,
        label: str | None = None,
        truncated: bool = False,
        prompt_tokens: int = 0,
    ) -> Turn:
        return Turn(
            role=role,
            content=content,
            tokens=tokens,
            label=label,
            timestamp=time.time(),
            truncated=truncated,
            prompt_tokens=prompt_tokens,
        )

    def _finalize(
        self,
        tracker: BudgetTracker,
        final_answer: str,
        transcript: list[Turn],
        metadata: dict,
        budget_exhausted: bool = False,
    ) -> StrategyResult:
        meta = {**(tracker.plan.metadata or {}), **metadata, **tracker.status()}
        return StrategyResult(
            final_answer=final_answer,
            tokens_spent=tracker.spent,
            prompt_tokens_spent=tracker.prompt_spent,
            transcript=transcript,
            metadata=meta,
            budget_exhausted=budget_exhausted or tracker.budget_exhausted,
            overshoot_flagged=tracker.overshoot_flagged(),
        )
