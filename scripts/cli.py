#!/usr/bin/env python3
"""CLI entrypoints: phase0 smoke test, full sweeps, transcript dump."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_preset(name: str) -> dict:
    from backend.config_loader import load_yaml

    cfg = load_yaml("sweeps.yaml")
    presets = cfg.get("presets", cfg)
    if name not in presets:
        raise SystemExit(f"Unknown preset: {name}. Available: {list(presets)}")
    return dict(presets[name])


def cmd_phase0(args: argparse.Namespace) -> None:
    from backend.config_loader import load_budget_config
    from backend.sweep_runner import SweepRunner

    bcfg = load_budget_config()
    p0 = bcfg.get("phase0", {})
    budget = int(args.budget or p0.get("budget", 512))
    n_seeds = int(args.seeds or p0.get("n_seeds", 3))
    n_tasks = int(args.tasks or p0.get("n_tasks", 50))
    model = args.model or p0.get("model", "qwen2.5-7b")
    strategies = args.strategies or p0.get("strategies", ["self_refine", "majority_vote"])

    math_dir = ROOT / "tasks" / "phase1_reasoning" / "math"
    if not any(math_dir.glob("*.json")):
        from scripts.generate_math_tasks import main as gen_math

        gen_math(n_tasks)

    runner = SweepRunner()
    sweep_id = runner.run_sweep(
        phase="phase1_reasoning",
        models=[model],
        strategies=list(strategies),
        budgets=[budget],
        n_seeds=n_seeds,
        task_limit=n_tasks,
        categories=["math"],
        resume=True,
    )
    print(f"Phase 0 sweep complete: {sweep_id}")
    dump_transcripts(sweep_id, limit=5)
    summarize_delta(sweep_id)


def dump_transcripts(sweep_id: str, limit: int = 5) -> None:
    from backend.db import get_db

    db = get_db()
    runs = db.query_runs(sweep_id=sweep_id, limit=limit)
    out_dir = ROOT / "results" / "transcripts" / sweep_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for run in runs:
        path = out_dir / f"{run['id']}.txt"
        turns = json.loads(run.get("transcript_json") or "[]")
        lines = [
            f"run={run['id']} model={run['model']} strategy={run['strategy']} task={run['task_id']}",
            f"budget={run['budget']} spent={run['tokens_spent']} correct={run['correct']}",
            f"answer={run['final_answer']} expected={run['expected_answer']}",
            "-" * 60,
        ]
        for t in turns:
            lines.append(
                f"[{t.get('label') or t.get('role')}] tokens={t.get('tokens')} trunc={t.get('truncated')}"
            )
            lines.append(t.get("content") or "")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {path}")


def summarize_delta(sweep_id: str) -> None:
    from backend.db import get_db
    from collections import defaultdict

    db = get_db()
    runs = db.query_runs(sweep_id=sweep_id, limit=100000)
    acc = defaultdict(list)
    budget_flags = []
    for r in runs:
        if r.get("correct") is None:
            continue
        acc[r["strategy"]].append(r["correct"])
        if r.get("tokens_spent") is not None and r.get("target_budget"):
            budget_flags.append(
                {
                    "strategy": r["strategy"],
                    "spent": r["tokens_spent"],
                    "target": r["target_budget"],
                    "overshoot": r["overshoot_flagged"],
                }
            )
    print("\n=== Accuracy by strategy ===")
    for s, vals in sorted(acc.items()):
        mean = sum(vals) / len(vals) if vals else 0
        print(f"  {s}: {mean:.1%} (n={len(vals)})")
    if "majority_vote" in acc and "self_refine" in acc:
        mv = sum(acc["majority_vote"]) / len(acc["majority_vote"])
        sr = sum(acc["self_refine"]) / len(acc["self_refine"])
        print(f"\nDelta_pp (majority_vote - self_refine): {(mv - sr) * 100:.1f} pp")
    if budget_flags:
        overs = sum(1 for b in budget_flags if b["overshoot"])
        avg_ratio = sum(b["spent"] / b["target"] for b in budget_flags) / len(budget_flags)
        print(f"Budget integrity: avg spent/target={avg_ratio:.2f}, overshoot_flagged={overs}/{len(budget_flags)}")


def cmd_sweep(args: argparse.Namespace) -> None:
    from backend.sweep_runner import SweepRunner

    kwargs: dict = {
        "resume": not args.no_resume,
    }
    if args.preset:
        p = _load_preset(args.preset)
        print(f"Using preset '{args.preset}': {p.get('description', '')}")
        kwargs.update(
            {
                "phase": p.get("phase", "phase1_reasoning"),
                "models": args.models or p.get("models"),
                "strategies": args.strategies or p.get("strategies"),
                "budgets": args.budgets or p.get("budgets"),
                "n_seeds": args.seeds if args.seeds is not None else p.get("n_seeds"),
                "task_limit": args.task_limit if args.task_limit is not None else p.get("task_limit"),
                "categories": args.categories if args.categories is not None else p.get("categories"),
            }
        )
    else:
        kwargs.update(
            {
                "phase": args.phase,
                "models": args.models,
                "strategies": args.strategies,
                "budgets": args.budgets,
                "n_seeds": args.seeds,
                "task_limit": args.task_limit,
                "categories": args.categories,
            }
        )

    runner = SweepRunner()
    sweep_id = runner.run_sweep(**kwargs)
    print(f"Sweep complete: {sweep_id}")
    summarize_delta(sweep_id)


def cmd_generate_tasks(_: argparse.Namespace) -> None:
    from backend.config_loader import load_tasks
    from scripts.generate_math_tasks import main as gen_math
    from scripts.generate_code_tasks import main as gen_code
    from scripts.generate_logic_tasks import main as gen_logic
    from scripts.generate_agent_tasks import main as gen_agent

    gen_math(50)
    gen_code()
    gen_logic(20)
    gen_agent()
    print("All tasks generated.")
    print(f"Phase1: {len(load_tasks('phase1_reasoning'))} tasks")
    print(f"Phase2: {len(load_tasks('phase2_agent'))} tasks")


def main() -> None:
    parser = argparse.ArgumentParser(description="SampleMoreStudio CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p0 = sub.add_parser("phase0", help="Phase 0 signal check")
    p0.add_argument("--model", default=None)
    p0.add_argument("--budget", type=int, default=None)
    p0.add_argument("--seeds", type=int, default=None)
    p0.add_argument("--tasks", type=int, default=None)
    p0.add_argument("--strategies", nargs="+", default=None)
    p0.set_defaults(func=cmd_phase0)

    sw = sub.add_parser("sweep", help="Run a full sweep")
    sw.add_argument("--preset", default=None, help="Named preset from config/sweeps.yaml")
    sw.add_argument("--phase", default="phase1_reasoning")
    sw.add_argument("--models", nargs="+", default=None)
    sw.add_argument("--strategies", nargs="+", default=None)
    sw.add_argument("--budgets", nargs="+", type=int, default=None)
    sw.add_argument("--seeds", type=int, default=None)
    sw.add_argument("--task-limit", type=int, default=None)
    sw.add_argument("--categories", nargs="+", default=None)
    sw.add_argument("--no-resume", action="store_true")
    sw.set_defaults(func=cmd_sweep)

    gt = sub.add_parser("generate-tasks", help="Generate all task suites")
    gt.set_defaults(func=cmd_generate_tasks)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
