#!/usr/bin/env python3
"""Export SQLite results to static JSON + optionally build frontend for offline deploy."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config_loader import load_tasks, load_yaml
from backend.db import get_db
from backend.stats import paired_strategy_delta, refine_before_after, strategy_accuracies
from backend.strategy_registry import list_strategies, plan_meta_for

OUT = ROOT / "export" / "out"
DATA = OUT / "data"


def dump() -> None:
    db = get_db()
    DATA.mkdir(parents=True, exist_ok=True)

    def write(name: str, payload: dict) -> None:
        (DATA / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    rows = db.leaderboard()
    enriched = []
    for r in rows:
        meta = plan_meta_for(str(r["strategy"]), int(r["budget"]))
        enriched.append(
            {
                **r,
                "truncation_rate": float(r.get("truncation_rate") or 0),
                "n_or_k": meta.get("n_or_k") or meta.get("n") or meta.get("k"),
                "per_sample_cap": meta.get("per_sample_cap") or meta.get("sample_cap"),
            }
        )
    write("leaderboard", {"data": enriched, "error": None})

    runs = db.query_runs(limit=100000)
    runs_list = []
    transcripts: dict = {}
    runs_full = []
    for r in runs:
        row = dict(r)
        tid = row["id"]
        try:
            tr = json.loads(row.get("transcript_json") or "[]")
        except json.JSONDecodeError:
            tr = []
        transcripts[tid] = {
            "run_id": tid,
            "transcript": tr,
            "final_answer": row.get("final_answer"),
            "expected_answer": row.get("expected_answer"),
            "correct": row.get("correct"),
            "tokens_spent": row.get("tokens_spent"),
            "target_budget": row.get("target_budget"),
            "overshoot_flagged": row.get("overshoot_flagged"),
            "strategy": row.get("strategy"),
            "model": row.get("model"),
            "task_id": row.get("task_id"),
            "budget": row.get("budget"),
        }
        full = dict(row)
        full["transcript"] = tr
        runs_full.append(full)
        row.pop("transcript_json", None)
        runs_list.append(row)

    write("runs", {"data": runs_list, "error": None})
    write("runs_full", {"data": runs_full, "error": None})
    write("transcripts", {"data": transcripts, "error": None})

    paired = paired_strategy_delta(runs, "majority_vote", "self_refine")
    delta_payload = {
        "paired_delta": paired,
        "strategy_accuracies": strategy_accuracies(runs),
        "refine_before_after": refine_before_after(runs),
        "hero": (
            f"At matched token budget, majority_vote beats self_refine by {paired['delta_pp']:.1f}pp "
            f"(95% CI [{paired['ci_low_pp']:.1f}, {paired['ci_high_pp']:.1f}])"
        ),
    }
    write("delta", {"data": delta_payload, "error": None})

    from collections import defaultdict

    agg: dict = defaultdict(list)
    for r in rows:
        agg[(r["strategy"], r["budget"])].append(r["accuracy"])
    curves: dict = {}
    for (strat, bud), vals in agg.items():
        curves.setdefault(strat, []).append(
            {"budget": bud, "accuracy": sum(vals) / len(vals), "n_runs": len(vals)}
        )
    for s in curves:
        curves[s].sort(key=lambda x: x["budget"])
    write("budget_curves", {"data": curves, "error": None})
    write("cost_summary", {"data": db.cost_summary(), "error": None})
    write("strategies", {"data": list_strategies(), "error": None})
    try:
        sweeps_cfg = load_yaml("sweeps.yaml")
        write("sweep_presets", {"data": sweeps_cfg.get("presets", sweeps_cfg), "error": None})
    except Exception:
        write("sweep_presets", {"data": {}, "error": None})

    tasks = []
    by_task: dict = defaultdict(list)
    for r in runs:
        if r.get("correct") is not None and not r.get("error"):
            by_task[r["task_id"]].append(float(r["correct"]))
    for t in load_tasks():
        rates = by_task.get(t.id, [])
        tasks.append(
            {
                **t.to_dict(),
                "pass_rate": sum(rates) / len(rates) if rates else None,
                "n_runs": len(rates),
            }
        )
    write("tasks", {"data": tasks, "error": None})
    print(f"Exported static JSON to {DATA}")


def _npm_cmd() -> str:
    if os.name == "nt":
        return "npm.cmd"
    return "npm"


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    npm = _npm_cmd()
    env = {**os.environ, "VITE_STATIC_MODE": "1", "VITE_STATIC_BASE": "/data"}
    subprocess.check_call([npm, "install"], cwd=str(frontend), shell=(os.name == "nt"), env=env)
    subprocess.check_call([npm, "run", "build"], cwd=str(frontend), shell=(os.name == "nt"), env=env)
    dist = frontend / "dist"
    for item in dist.iterdir():
        dest = OUT / item.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    # Ensure data/ survives next to built assets
    if not (OUT / "data").exists() and DATA.exists():
        shutil.copytree(DATA, OUT / "data")
    print(f"Static site ready at {OUT}")


if __name__ == "__main__":
    dump()
    if "--build" in sys.argv:
        build_frontend()
