"""Majority-Vote@K: K independent samples, free counting selection."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import extract_answer, majority_vote
from backend.strategies.base import Strategy
from backend.config_loader import load_budget_config
from backend.token_budget import BudgetTracker, majority_vote_plan, resolve_caps_from_config
from backend.types import StrategyResult, Task


class MajorityVoteStrategy(Strategy):
    name = "majority_vote"
    phase = "phase1_reasoning"

    def __init__(self, sample_cap: int | None = None):
        self.sample_cap = sample_cap

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        if self.sample_cap is None:
            sample_cap, _ = resolve_caps_from_config(token_budget, load_budget_config())
        else:
            sample_cap = self.sample_cap
        plan = majority_vote_plan(token_budget, sample_cap)
        tracker = BudgetTracker(plan)
        domain = task.category if task.category in ("math", "logic", "code") else "math"
        system = self._system_prompt(task)
        user = self._user_prompt(task)
        transcript = [
            self._make_turn("system", system, 0, label="system"),
            self._make_turn("user", user, 0, label="user"),
        ]
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        k = plan.n_samples or 1
        samples: list[str] = []
        extracted: list[str] = []

        for i in range(k):
            cap = tracker.next_cap()
            if cap <= 0:
                break
            gen = model.generate(messages, max_tokens=cap, seed=i)
            tracker.record(gen.completion_tokens, gen.prompt_tokens)
            samples.append(gen.content)
            ans = extract_answer(gen.content, domain=domain)
            extracted.append(ans)
            transcript.append(
                self._make_turn(
                    "assistant",
                    gen.content,
                    gen.completion_tokens,
                    label=f"sample_{i + 1}_of_{k}",
                    truncated=gen.truncated,
                    prompt_tokens=gen.prompt_tokens,
                )
            )

        winner, breakdown = majority_vote(extracted, domain=domain)
        transcript.append(
            self._make_turn(
                "assistant",
                f"Majority vote result: {breakdown}",
                0,
                label="final_vote",
            )
        )
        return self._finalize(
            tracker,
            winner,
            transcript,
            metadata={
                "k": len(samples),
                "extracted_samples": extracted,
                "vote_breakdown": breakdown,
            },
        )
