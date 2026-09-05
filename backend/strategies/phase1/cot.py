"""Chain-of-Thought: single generation capped at B completion tokens."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import extract_answer
from backend.strategies.base import Strategy
from backend.token_budget import BudgetTracker, cot_plan
from backend.types import StrategyResult, Task


class CotStrategy(Strategy):
    name = "cot"
    phase = "phase1_reasoning"

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        plan = cot_plan(token_budget)
        tracker = BudgetTracker(plan)
        transcript = [
            self._make_turn("system", self._system_prompt(task), 0, label="system"),
            self._make_turn("user", self._user_prompt(task), 0, label="user"),
        ]
        messages = [
            {"role": "system", "content": self._system_prompt(task)},
            {"role": "user", "content": self._user_prompt(task)},
        ]
        cap = tracker.next_cap()
        gen = model.generate(messages, max_tokens=cap)
        tracker.record(gen.completion_tokens, gen.prompt_tokens)
        transcript.append(
            self._make_turn(
                "assistant",
                gen.content,
                gen.completion_tokens,
                label="cot",
                truncated=gen.truncated,
                prompt_tokens=gen.prompt_tokens,
            )
        )
        domain = task.category if task.category in ("math", "logic", "code") else "math"
        answer = extract_answer(gen.content, domain=domain)
        return self._finalize(
            tracker,
            answer,
            transcript,
            metadata={"truncated": gen.truncated, "finish_reason": gen.finish_reason},
        )
