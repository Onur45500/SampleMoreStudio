"""Leaderboard and analytics routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.db import get_db
from backend.stats import paired_strategy_delta, refine_before_after, strategy_accuracies
from backend.strategy_registry import plan_meta_for

router = APIRouter(prefix="/api", tags=["leaderboard"])


def _enrich_leaderboard_row(row: dict[str, Any]) -> dict[str, Any]:
    meta = plan_meta_for(str(row["strategy"]), int(row["budget"]))
    row = dict(row)
    row["n_or_k"] = meta.get("n_or_k") or meta.get("n") or meta.get("k")
    row["per_sample_cap"] = meta.get("per_sample_cap") or meta.get("sample_cap")
    row["allocation_formula"] = meta.get("formula")
    row["truncation_rate"] = float(row.get("truncation_rate") or 0)
    return row


@router.get("/leaderboard")
def leaderboard(
    phase: str | None = None,
    model: str | None = None,
    strategy: str | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    rows = get_db().leaderboard(phase=phase, model=model, strategy=strategy, budget=budget)
    return {"data": [_enrich_leaderboard_row(r) for r in rows], "error": None}


@router.get("/delta")
def delta(
    phase: str | None = None,
    budget: int | None = None,
    strategy_a: str = "majority_vote",
    strategy_b: str = "self_refine",
) -> dict[str, Any]:
    db = get_db()
    runs = db.query_runs(phase=phase, budget=budget, limit=100000)
    paired = paired_strategy_delta(runs, strategy_a, strategy_b, budget=budget)
    accs = strategy_accuracies(runs, budget=budget)
    refine = refine_before_after(runs)

    # Truncation by strategy at this budget
    trunc: dict[str, list[float]] = {}
    for r in runs:
        if r.get("correct") is None:
            continue
        trunc.setdefault(r["strategy"], []).append(float(r.get("truncated_any") or 0))
    truncation_by_strategy = {
        s: {"truncation_rate": sum(v) / len(v) if v else 0.0, "n": len(v)} for s, v in trunc.items()
    }

    hero = (
        f"At matched token budget"
        + (f" B={budget}" if budget else "")
        + f", {strategy_a} beats {strategy_b} by {paired['delta_pp']:.1f}pp "
        f"(95% CI [{paired['ci_low_pp']:.1f}, {paired['ci_high_pp']:.1f}], n_pairs={paired['n_pairs']})"
    )
    return {
        "data": {
            "paired_delta": paired,
            "strategy_accuracies": accs,
            "refine_before_after": refine,
            "truncation_by_strategy": truncation_by_strategy,
            "hero": hero,
        },
        "error": None,
    }


@router.get("/budget-curves")
def budget_curves(phase: str | None = None, model: str | None = None) -> dict[str, Any]:
    rows = get_db().leaderboard(phase=phase, model=model)
    curves: dict[str, list] = {}
    for r in rows:
        curves.setdefault(r["strategy"], []).append(
            {
                "budget": r["budget"],
                "accuracy": r["accuracy"],
                "n_runs": r["n_runs"],
                "model": r["model"],
                "truncation_rate": float(r.get("truncation_rate") or 0),
            }
        )
    if model is None:
        from collections import defaultdict

        agg: dict[tuple, list] = defaultdict(list)
        trunc_agg: dict[tuple, list] = defaultdict(list)
        for r in rows:
            key = (r["strategy"], r["budget"])
            agg[key].append(r["accuracy"])
            trunc_agg[key].append(float(r.get("truncation_rate") or 0))
        curves = {}
        for (strat, bud), vals in agg.items():
            curves.setdefault(strat, []).append(
                {
                    "budget": bud,
                    "accuracy": sum(vals) / len(vals),
                    "n_runs": len(vals),
                    "truncation_rate": sum(trunc_agg[(strat, bud)]) / len(trunc_agg[(strat, bud)]),
                }
            )
        for strat in curves:
            curves[strat].sort(key=lambda x: x["budget"])
    return {"data": curves, "error": None}


@router.get("/cost/summary")
def cost_summary() -> dict[str, Any]:
    return {"data": get_db().cost_summary(), "error": None}


@router.get("/strategies")
def strategies(phase: str | None = None) -> dict[str, Any]:
    from backend.strategy_registry import list_strategies

    return {"data": list_strategies(phase), "error": None}


@router.get("/sweeps/presets")
def sweep_presets() -> dict[str, Any]:
    from backend.config_loader import load_yaml

    try:
        cfg = load_yaml("sweeps.yaml")
    except FileNotFoundError:
        cfg = {"presets": {}}
    presets = cfg.get("presets", cfg)
    return {"data": presets, "error": None}
