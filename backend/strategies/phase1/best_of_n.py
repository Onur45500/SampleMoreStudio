"""Best-of-N: N independent samples + self-selection call within budget B."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import extract_answer
from backend.strategies.base import Strategy
from backend.config_loader import load_budget_config
from backend.token_budget import BudgetTracker, best_of_n_plan, resolve_caps_from_config
from backend.types import StrategyResult, Task


class BestOfNStrategy(Strategy):
    name = "best_of_n"
    phase = "phase1_reasoning"

    def __init__(self, sample_cap: int | None = None, selection_cap: int | None = None):
        self.sample_cap = sample_cap
        self.selection_cap = selection_cap

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        if self.sample_cap is None or self.selection_cap is None:
            sc, sel = resolve_caps_from_config(token_budget, load_budget_config())
            sample_cap = self.sample_cap if self.sample_cap is not None else sc
            selection_cap = self.selection_cap if self.selection_cap is not None else sel
        else:
            sample_cap, selection_cap = self.sample_cap, self.selection_cap
        plan = best_of_n_plan(token_budget, sample_cap, selection_cap)
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

        n = plan.n_samples or 1
        samples: list[str] = []
        extracted: list[str] = []

        for i in range(n):
            cap = tracker.next_cap()
            if cap <= 0:
                break
            gen = model.generate(messages, max_tokens=cap, seed=i)
            tracker.record(gen.completion_tokens, gen.prompt_tokens)
            samples.append(gen.content)
            extracted.append(extract_answer(gen.content, domain=domain))
            transcript.append(
                self._make_turn(
                    "assistant",
                    gen.content,
                    gen.completion_tokens,
                    label=f"sample_{i + 1}_of_{n}",
                    truncated=gen.truncated,
                    prompt_tokens=gen.prompt_tokens,
                )
            )

        if not samples:
            return self._finalize(tracker, "", transcript, {"n": 0}, budget_exhausted=True)

        if len(samples) == 1 or tracker.remaining <= 0:
            return self._finalize(
                tracker,
                extracted[0],
                transcript,
                metadata={"n": len(samples), "selected_index": 0, "selection": "only_sample"},
            )

        # Self-selection
        listing = "\n\n".join(
            f"--- Candidate {i + 1} ---\n{s}" for i, s in enumerate(samples)
        )
        sel_user = (
            f"Problem:\n{task.prompt}\n\n"
            f"Below are {len(samples)} independent candidate solutions.\n"
            f"{listing}\n\n"
            "Select the best candidate. Reply with the candidate number and then "
            "copy its final answer. End with Answer: <final>."
        )
        cap = tracker.next_cap(self.selection_cap)
        sel_msgs = [
            {"role": "system", "content": "You are an expert grader selecting the best solution."},
            {"role": "user", "content": sel_user},
        ]
        sgen = model.generate(sel_msgs, max_tokens=cap)
        tracker.record(sgen.completion_tokens, sgen.prompt_tokens)
        transcript.append(
            self._make_turn(
                "assistant",
                sgen.content,
                sgen.completion_tokens,
                label="self_selection",
                truncated=sgen.truncated,
                prompt_tokens=sgen.prompt_tokens,
            )
        )
        selected = extract_answer(sgen.content, domain=domain)
        # Fallback: if selection extraction empty, pick first
        if not selected and extracted:
            selected = extracted[0]
        return self._finalize(
            tracker,
            selected,
            transcript,
            metadata={
                "n": len(samples),
                "extracted_samples": extracted,
                "selection_raw": sgen.content[:500],
            },
        )
