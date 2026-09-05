"""Statistics helpers — paired deltas with bootstrap CIs."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np


def bootstrap_ci(values: list[float], n_boot: int = 2000, alpha: float = 0.05, seed: int = 0) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "low": 0.0, "high": 0.0, "n": 0}
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    means = []
    n = len(arr)
    for _ in range(n_boot):
        sample = rng.choice(arr, size=n, replace=True)
        means.append(float(sample.mean()))
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return {"mean": float(arr.mean()), "low": lo, "high": hi, "n": n}


def paired_strategy_delta(
    runs: list[dict[str, Any]],
    strategy_a: str,
    strategy_b: str,
    budget: int | None = None,
) -> dict[str, Any]:
    """Paired-by-task (and seed) accuracy delta: mean(acc_a - acc_b)."""
    # key: (task_id, seed, model, budget) -> strategy -> correct
    buckets: dict[tuple, dict[str, float]] = defaultdict(dict)
    for r in runs:
        if r.get("correct") is None or r.get("error"):
            continue
        if budget is not None and r.get("budget") != budget:
            continue
        if r["strategy"] not in (strategy_a, strategy_b):
            continue
        key = (r["task_id"], r.get("seed", 0), r["model"], r["budget"])
        buckets[key][r["strategy"]] = float(r["correct"])

    deltas = []
    for key, strats in buckets.items():
        if strategy_a in strats and strategy_b in strats:
            deltas.append(strats[strategy_a] - strats[strategy_b])

    ci = bootstrap_ci(deltas)
    return {
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "delta_pp": ci["mean"] * 100,
        "ci_low_pp": ci["low"] * 100,
        "ci_high_pp": ci["high"] * 100,
        "n_pairs": ci["n"],
        "budget": budget,
    }


def strategy_accuracies(runs: list[dict[str, Any]], budget: int | None = None) -> list[dict[str, Any]]:
    groups: dict[tuple, list[float]] = defaultdict(list)
    for r in runs:
        if r.get("correct") is None or r.get("error"):
            continue
        if budget is not None and r.get("budget") != budget:
            continue
        key = (r["model"], r["strategy"], r["budget"], r["phase"])
        groups[key].append(float(r["correct"]))
    out = []
    for (model, strategy, b, phase), vals in groups.items():
        ci = bootstrap_ci(vals)
        out.append(
            {
                "model": model,
                "strategy": strategy,
                "budget": b,
                "phase": phase,
                "accuracy": ci["mean"],
                "ci_low": ci["low"],
                "ci_high": ci["high"],
                "n": ci["n"],
            }
        )
    return out


def refine_before_after(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare initial vs final answer correctness inside self_refine / reflexion."""
    from backend.answer_extraction import answers_equal

    initial_correct = []
    final_correct = []
    for r in runs:
        if r.get("strategy") not in ("self_refine", "reflexion"):
            continue
        if not r.get("metadata_json"):
            continue
        import json

        meta = json.loads(r["metadata_json"]) if isinstance(r["metadata_json"], str) else r["metadata_json"]
        init = meta.get("initial_answer")
        final = meta.get("final_answer") or r.get("final_answer")
        expected = r.get("expected_answer")
        domain = "math"
        if init is None or expected is None:
            continue
        initial_correct.append(1.0 if answers_equal(str(init), str(expected), domain) else 0.0)
        final_correct.append(1.0 if answers_equal(str(final), str(expected), domain) else 0.0)

    return {
        "initial_accuracy": float(np.mean(initial_correct)) if initial_correct else 0.0,
        "final_accuracy": float(np.mean(final_correct)) if final_correct else 0.0,
        "n": len(initial_correct),
        "delta_pp": (
            (float(np.mean(final_correct)) - float(np.mean(initial_correct))) * 100
            if initial_correct
            else 0.0
        ),
    }
