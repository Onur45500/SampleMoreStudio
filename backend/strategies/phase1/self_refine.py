"""Self-Refine: initial + R rounds of (critique, revision), even budget split."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import extract_answer
from backend.strategies.base import Strategy
from backend.token_budget import BudgetTracker, self_refine_plan
from backend.types import StrategyResult, Task


class SelfRefineStrategy(Strategy):
    name = "self_refine"
    phase = "phase1_reasoning"

    def __init__(self, rounds: int = 3, split: str = "even"):
        self.rounds = rounds
        self.split = split  # type: ignore[assignment]

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        plan = self_refine_plan(token_budget, rounds=self.rounds, split=self.split)  # type: ignore[arg-type]
        tracker = BudgetTracker(plan)
        domain = task.category if task.category in ("math", "logic", "code") else "math"
        system = self._system_prompt(task)
        user = self._user_prompt(task)
        transcript = [
            self._make_turn("system", system, 0, label="system"),
            self._make_turn("user", user, 0, label="user"),
        ]

        # Initial generation
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        cap = tracker.next_cap()
        if cap <= 0:
            return self._finalize(tracker, "", transcript, {"error": "no_budget"}, budget_exhausted=True)

        gen = model.generate(messages, max_tokens=cap)
        tracker.record(gen.completion_tokens, gen.prompt_tokens)
        draft = gen.content
        initial_answer = extract_answer(draft, domain=domain)
        transcript.append(
            self._make_turn(
                "assistant",
                draft,
                gen.completion_tokens,
                label="initial",
                truncated=gen.truncated,
                prompt_tokens=gen.prompt_tokens,
            )
        )

        answers_over_rounds = [initial_answer]

        for r in range(1, self.rounds + 1):
            # Critique
            cap = tracker.next_cap()
            if cap <= 0:
                break
            critique_user = (
                f"Here is a candidate solution to the problem:\n\n{draft}\n\n"
                "Critique this solution. List any errors or improvements. "
                "Do NOT provide a revised final answer yet — only critique."
            )
            critique_msgs = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": draft},
                {"role": "user", "content": critique_user},
            ]
            cgen = model.generate(critique_msgs, max_tokens=cap)
            tracker.record(cgen.completion_tokens, cgen.prompt_tokens)
            critique = cgen.content
            transcript.append(
                self._make_turn(
                    "assistant",
                    critique,
                    cgen.completion_tokens,
                    label=f"critique_round_{r}",
                    truncated=cgen.truncated,
                    prompt_tokens=cgen.prompt_tokens,
                )
            )

            # Revision
            cap = tracker.next_cap()
            if cap <= 0:
                break
            revise_user = (
                f"Critique:\n{critique}\n\n"
                "Revise your solution based on the critique. "
                "Provide the improved full solution and end with Answer: <final>."
            )
            revise_msgs = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": draft},
                {"role": "user", "content": critique_user},
                {"role": "assistant", "content": critique},
                {"role": "user", "content": revise_user},
            ]
            rgen = model.generate(revise_msgs, max_tokens=cap)
            tracker.record(rgen.completion_tokens, rgen.prompt_tokens)
            draft = rgen.content
            answers_over_rounds.append(extract_answer(draft, domain=domain))
            transcript.append(
                self._make_turn(
                    "assistant",
                    draft,
                    rgen.completion_tokens,
                    label=f"revision_round_{r}",
                    truncated=rgen.truncated,
                    prompt_tokens=rgen.prompt_tokens,
                )
            )

        final = extract_answer(draft, domain=domain)
        changed = initial_answer != final
        return self._finalize(
            tracker,
            final,
            transcript,
            metadata={
                "rounds": self.rounds,
                "initial_answer": initial_answer,
                "final_answer": final,
                "answer_changed": changed,
                "answers_over_rounds": answers_over_rounds,
            },
            budget_exhausted=tracker.budget_exhausted,
        )
