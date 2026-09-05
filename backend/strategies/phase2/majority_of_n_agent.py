"""Majority-of-N independent agent attempts within shared budget."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import majority_vote
from backend.config_loader import load_budget_config
from backend.strategies.phase2.agent_common import AgentLoopMixin
from backend.token_budget import BudgetPlan, BudgetTracker, majority_of_n_agent_plan, resolve_caps_from_config
from backend.types import StrategyResult, Task


class MajorityOfNAgentStrategy(AgentLoopMixin):
    name = "majority_of_n_agent"
    phase = "phase2_agent"

    def __init__(self, sample_cap: int | None = None):
        self.sample_cap = sample_cap

    def run(self, task: Task, model: ModelAdapter, token_budget: int) -> StrategyResult:
        if self.sample_cap is None:
            sc, _ = resolve_caps_from_config(token_budget, load_budget_config())
            # Fewer fuller attempts: at least half of B or 2x sample cap
            sample_cap = max(sc * 2, 256, token_budget // 2)
        else:
            sample_cap = max(self.sample_cap, 192)
        plan = majority_of_n_agent_plan(token_budget, sample_cap=sample_cap)
        n = plan.n_samples or 1
        domain = task.grader_params.get("domain", "math")
        answers: list[str] = []
        all_transcript = []
        total_tools = 0
        global_tracker = BudgetTracker(
            BudgetPlan(total_budget=token_budget, allocations=plan.allocations, labels=plan.labels)
        )

        for i, alloc in enumerate(plan.allocations):
            remaining = global_tracker.remaining
            if remaining <= 0:
                break
            attempt_budget = min(alloc, remaining)
            # 3–4 larger reasoning turns beat 6 tiny truncated ones
            n_turns = 4
            per = max(32, attempt_budget // n_turns)
            allocations = [per] * n_turns
            allocations[0] += max(0, attempt_budget - per * n_turns)
            attempt_plan = BudgetPlan(
                total_budget=attempt_budget,
                allocations=allocations,
                labels=[f"a{i+1}_t{j+1}" for j in range(n_turns)],
            )
            local = BudgetTracker(attempt_plan)
            answer, transcript, meta = self.run_agent_loop(
                task,
                model,
                local,
                extra_system=f"Independent attempt {i + 1} of {n}. Use tools before answering.",
                max_turns=n_turns,
                label_prefix=f"attempt_{i + 1}_",
            )
            global_tracker.spent += local.spent
            global_tracker.prompt_spent += local.prompt_spent
            global_tracker.call_index += local.call_index
            answers.append(answer)
            all_transcript.extend(transcript)
            total_tools += meta.get("tool_calls", 0)

        winner, breakdown = majority_vote(answers, domain=domain)
        all_transcript.append(
            self._make_turn("assistant", f"Vote: {breakdown}", 0, label="final_vote")
        )
        return self._finalize(
            global_tracker,
            winner,
            all_transcript,
            {"n": len(answers), "answers": answers, "vote_breakdown": breakdown, "tool_calls": total_tools},
            global_tracker.budget_exhausted,
        )
