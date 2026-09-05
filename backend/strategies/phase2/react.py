"""ReAct scaffold for Phase 2."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.strategies.phase2.agent_common import AgentLoopMixin
from backend.token_budget import BudgetTracker, agent_loop_plan
from backend.types import StrategyResult, Task


class ReactStrategy(AgentLoopMixin):
    name = "react"
    phase = "phase2_agent"

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        plan = agent_loop_plan(token_budget, max_turns=12)
        tracker = BudgetTracker(plan)
        answer, transcript, meta = self.run_agent_loop(
            task,
            model,
            tracker,
            extra_system="Use interleaved Thought → Action → Observation (ReAct style).",
        )
        return self._finalize(tracker, answer, transcript, meta, budget_exhausted=tracker.budget_exhausted)
