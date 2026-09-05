"""Reflexion: agent attempt + self-critique + retry within budget."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.strategies.phase2.agent_common import AgentLoopMixin
from backend.token_budget import BudgetTracker, agent_loop_plan
from backend.types import StrategyResult, Task


class ReflexionStrategy(AgentLoopMixin):
    name = "reflexion"
    phase = "phase2_agent"

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        # Split budget roughly in half: attempt 1, then critique+retry
        half = max(1, token_budget // 2)
        plan1 = agent_loop_plan(half, max_turns=6)
        tracker = BudgetTracker(plan1)
        answer1, transcript1, meta1 = self.run_agent_loop(
            task, model, tracker, extra_system="First attempt.", label_prefix="attempt1_"
        )

        remaining = token_budget - tracker.spent
        if remaining <= 0:
            return self._finalize(
                tracker,
                answer1,
                transcript1,
                {**meta1, "reflexion_rounds": 0, "initial_answer": answer1},
                budget_exhausted=True,
            )

        # Critique
        critique_cap = min(remaining // 3, remaining)
        registry = self._registry(task)
        system = self._agent_system(task, registry)
        critique_msgs = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Task: {task.prompt}\n\nYour previous answer was: {answer1}\n"
                    "Critique what may be wrong. Do not give the final answer yet."
                ),
            },
        ]
        # Rebind tracker to remaining full budget for bookkeeping
        from backend.token_budget import BudgetPlan

        full_plan = BudgetPlan(total_budget=token_budget, allocations=[], labels=[])
        full_tracker = BudgetTracker(full_plan)
        full_tracker.spent = tracker.spent
        full_tracker.prompt_spent = tracker.prompt_spent

        transcript = list(transcript1)
        if critique_cap > 0:
            cgen = model.generate(critique_msgs, max_tokens=critique_cap)
            full_tracker.record(cgen.completion_tokens, cgen.prompt_tokens)
            critique = cgen.content
            transcript.append(
                self._make_turn(
                    "assistant",
                    critique,
                    cgen.completion_tokens,
                    label="self_critique",
                    truncated=cgen.truncated,
                    prompt_tokens=cgen.prompt_tokens,
                )
            )
        else:
            critique = ""

        remaining2 = token_budget - full_tracker.spent
        plan2 = agent_loop_plan(remaining2, max_turns=6)
        # Sync spent into a fresh tracker that still respects total B
        tracker2 = BudgetTracker(
            BudgetPlan(total_budget=token_budget, allocations=plan2.allocations, labels=plan2.labels)
        )
        tracker2.spent = full_tracker.spent
        tracker2.prompt_spent = full_tracker.prompt_spent

        answer2, transcript2, meta2 = self.run_agent_loop(
            task,
            model,
            tracker2,
            extra_system=f"Reflection from prior attempt:\n{critique}\nTry again carefully.",
            label_prefix="attempt2_",
        )
        merged = transcript + [t for t in transcript2 if t.label and t.label.startswith("attempt2_")]
        return self._finalize(
            tracker2,
            answer2 or answer1,
            merged,
            {
                "tool_calls": meta1.get("tool_calls", 0) + meta2.get("tool_calls", 0),
                "initial_answer": answer1,
                "final_answer": answer2,
                "answer_changed": answer1 != answer2,
                "reflexion_rounds": 1,
            },
            tracker2.budget_exhausted,
        )
