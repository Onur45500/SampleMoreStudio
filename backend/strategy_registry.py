"""Strategy registry — instantiate strategies from config."""
from __future__ import annotations

from typing import Any

from backend.config_loader import load_budget_config, load_strategies_config
from backend.strategies.base import Strategy
from backend.strategies.phase1.best_of_n import BestOfNStrategy
from backend.strategies.phase1.cot import CotStrategy
from backend.strategies.phase1.majority_vote import MajorityVoteStrategy
from backend.strategies.phase1.self_refine import SelfRefineStrategy
from backend.token_budget import resolve_caps_from_config


def _phase2_imports():
    from backend.strategies.phase2.majority_of_n_agent import MajorityOfNAgentStrategy
    from backend.strategies.phase2.plan_then_act import PlanThenActStrategy
    from backend.strategies.phase2.react import ReactStrategy
    from backend.strategies.phase2.reflexion import ReflexionStrategy

    return {
        "react": ReactStrategy,
        "plan_then_act": PlanThenActStrategy,
        "reflexion": ReflexionStrategy,
        "majority_of_n_agent": MajorityOfNAgentStrategy,
    }


PHASE1 = {
    "cot": CotStrategy,
    "self_refine": SelfRefineStrategy,
    "best_of_n": BestOfNStrategy,
    "majority_vote": MajorityVoteStrategy,
}


def build_strategy(
    strategy_id: str,
    phase: str = "phase1_reasoning",
    budget: int | None = None,
    **overrides: Any,
) -> Strategy:
    budgets = load_budget_config()
    rounds = int(overrides.get("rounds", budgets.get("self_refine_rounds", 3)))
    split = overrides.get("split", budgets.get("self_refine_split", "even"))

    # Caps resolved at run() via budget when scale_with_budget; constructors keep
    # optional absolute overrides for tests.
    sample_cap = overrides.get("sample_cap")
    selection_cap = overrides.get("selection_cap")
    if budget is not None and sample_cap is None:
        sample_cap, selection_cap = resolve_caps_from_config(budget, budgets)
    elif sample_cap is None:
        sample_cap = int(budgets.get("sample_token_floor", budgets.get("sample_token_cap", 128)))
        selection_cap = int(budgets.get("selection_token_floor", budgets.get("selection_token_cap", 64)))
    else:
        sample_cap = int(sample_cap)
        selection_cap = int(selection_cap if selection_cap is not None else budgets.get("selection_token_floor", 64))

    if phase == "phase1_reasoning" or strategy_id in PHASE1:
        if strategy_id == "cot":
            return CotStrategy()
        if strategy_id == "self_refine":
            return SelfRefineStrategy(rounds=rounds, split=split)
        if strategy_id == "best_of_n":
            return BestOfNStrategy(sample_cap=None, selection_cap=None)  # scale in run()
        if strategy_id == "majority_vote":
            return MajorityVoteStrategy(sample_cap=None)

    phase2 = _phase2_imports()
    if strategy_id in phase2:
        cls = phase2[strategy_id]
        if strategy_id == "majority_of_n_agent":
            return cls(sample_cap=None)  # scale in run()
        return cls()

    raise KeyError(f"Unknown strategy: {strategy_id} for phase {phase}")


def list_strategies(phase: str | None = None) -> list[dict[str, Any]]:
    cfg = load_strategies_config()
    out = []
    for ph, items in cfg.items():
        if phase and ph != phase:
            continue
        for item in items:
            if item.get("enabled", True):
                out.append({**item, "phase": ph})
    return out


def plan_meta_for(strategy_id: str, budget: int) -> dict[str, Any]:
    """Allocation metadata for API (n_or_k, per_sample_cap) without running a model."""
    from backend.token_budget import best_of_n_plan, cot_plan, majority_of_n_agent_plan, majority_vote_plan, self_refine_plan

    budgets = load_budget_config()
    sample_cap, selection_cap = resolve_caps_from_config(budget, budgets)
    if strategy_id == "cot":
        return {**(cot_plan(budget).metadata or {}), "n_or_k": 1, "per_sample_cap": budget}
    if strategy_id == "self_refine":
        p = self_refine_plan(budget, rounds=int(budgets.get("self_refine_rounds", 3)))
        return {**(p.metadata or {}), "n_or_k": 1, "per_sample_cap": p.allocations[0] if p.allocations else 0}
    if strategy_id == "best_of_n":
        return dict(best_of_n_plan(budget, sample_cap, selection_cap).metadata or {})
    if strategy_id == "majority_vote":
        return dict(majority_vote_plan(budget, sample_cap).metadata or {})
    if strategy_id == "majority_of_n_agent":
        agent_cap = max(sample_cap * 2, 256, budget // 2)
        return dict(majority_of_n_agent_plan(budget, sample_cap=agent_cap).metadata or {})
    return {"n_or_k": None, "per_sample_cap": None}
