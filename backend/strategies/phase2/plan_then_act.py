"""Plan-then-Act: spend first slice on a plan, then execute."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.strategies.phase2.agent_common import AgentLoopMixin
from backend.token_budget import BudgetTracker, agent_loop_plan
from backend.types import StrategyResult, Task


class PlanThenActStrategy(AgentLoopMixin):
    name = "plan_then_act"
    phase = "phase2_agent"

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        plan = agent_loop_plan(token_budget, max_turns=12)
        tracker = BudgetTracker(plan)
        registry = self._registry(task)
        system = self._agent_system(task, registry) + "\nFirst write a short plan, then execute it with tools."
        transcript = [
            self._make_turn("system", system, 0, label="system"),
            self._make_turn("user", task.prompt, 0, label="user"),
        ]
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": task.prompt + "\n\nFirst, output a numbered plan only (no tools yet).",
            },
        ]
        cap = tracker.next_cap()
        if cap > 0:
            gen = model.generate(messages, max_tokens=cap)
            tracker.record(gen.completion_tokens, gen.prompt_tokens)
            transcript.append(
                self._make_turn(
                    "assistant",
                    gen.content,
                    gen.completion_tokens,
                    label="plan",
                    truncated=gen.truncated,
                    prompt_tokens=gen.prompt_tokens,
                )
            )
            plan_text = gen.content
        else:
            plan_text = ""

        answer, loop_transcript, meta = self.run_agent_loop(
            task,
            model,
            tracker,
            extra_system=f"Follow this plan:\n{plan_text}",
            label_prefix="exec_",
        )
        # Avoid duplicating system/user — keep plan turn + execution turns after first user
        merged = transcript + [t for t in loop_transcript if t.label and t.label.startswith("exec_")]
        return self._finalize(tracker, answer, merged, {**meta, "plan": plan_text[:500]}, tracker.budget_exhausted)
