"""Sweep orchestration with resume via deterministic run keys."""
from __future__ import annotations

import hashlib
import json
import time
import traceback
import uuid
from dataclasses import asdict
from typing import Any

from backend.adapters.litellm_adapter import ModelAdapter
from backend.config_loader import (
    get_model,
    load_budget_config,
    load_models,
    load_tasks,
    load_temperature,
)
from backend.db import Database, get_db
from backend.graders import grade
from backend.strategy_registry import build_strategy
from backend.types import Task


def make_run_key(
    config_hash: str,
    model: str,
    strategy: str,
    task_id: str,
    budget: int,
    seed: int,
) -> str:
    raw = f"{config_hash}|{model}|{strategy}|{task_id}|{budget}|{seed}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def make_config_hash(config: dict[str, Any]) -> str:
    blob = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


class SweepRunner:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run_sweep(
        self,
        phase: str = "phase1_reasoning",
        models: list[str] | None = None,
        strategies: list[str] | None = None,
        budgets: list[int] | None = None,
        n_seeds: int | None = None,
        task_limit: int | None = None,
        categories: list[str] | None = None,
        sweep_id: str | None = None,
        resume: bool = True,
    ) -> str:
        self._stop = False
        bcfg = load_budget_config()
        budgets = budgets or list(bcfg.get("budgets", [512]))
        n_seeds = n_seeds if n_seeds is not None else int(bcfg.get("default_n_seeds", 3))
        temperature = load_temperature()

        model_cfgs = load_models(enabled_only=True)
        if models:
            model_cfgs = [get_model(m) for m in models]

        if strategies is None:
            if phase == "phase1_reasoning":
                strategies = ["cot", "self_refine", "best_of_n", "majority_vote"]
            else:
                strategies = ["react", "plan_then_act", "reflexion", "majority_of_n_agent"]

        tasks = load_tasks(phase=phase)
        if categories:
            tasks = [
                t
                for t in tasks
                if t.category in categories or any(c in t.category for c in categories)
            ]
        if task_limit is not None:
            tasks = tasks[:task_limit]

        config = {
            "phase": phase,
            "models": [m.id for m in model_cfgs],
            "strategies": strategies,
            "budgets": budgets,
            "n_seeds": n_seeds,
            "task_ids": [t.id for t in tasks],
            "temperature": temperature,
            "sample_token_cap": bcfg.get("sample_token_cap"),
            "selection_token_cap": bcfg.get("selection_token_cap"),
            "self_refine_rounds": bcfg.get("self_refine_rounds"),
        }
        config_hash = make_config_hash(config)
        sweep_id = sweep_id or f"sweep_{config_hash}_{int(time.time())}"

        combos = []
        for m in model_cfgs:
            for s in strategies:
                for t in tasks:
                    for b in budgets:
                        for seed in range(n_seeds):
                            combos.append((m, s, t, b, seed))

        total = len(combos)
        self.db.upsert_sweep(
            {
                "id": sweep_id,
                "config_hash": config_hash,
                "phase": phase,
                "status": "running",
                "config_json": json.dumps(config),
                "total_runs": total,
                "completed_runs": 0,
                "created_at": time.time(),
                "started_at": time.time(),
                "finished_at": None,
                "error": None,
            }
        )
        self.db.update_progress(
            sweep_id=sweep_id,
            status="running",
            completed=0,
            total=total,
            log_tail=[],
        )
        self.db.append_log(f"Starting sweep {sweep_id}: {total} runs")

        completed = 0
        for model_cfg, strategy_id, task, budget, seed in combos:
            if self._stop:
                self.db.append_log("Stop requested — pausing sweep")
                self.db.upsert_sweep(
                    {
                        "id": sweep_id,
                        "config_hash": config_hash,
                        "phase": phase,
                        "status": "stopped",
                        "config_json": json.dumps(config),
                        "total_runs": total,
                        "completed_runs": completed,
                        "created_at": time.time(),
                        "started_at": None,
                        "finished_at": time.time(),
                        "error": "stopped_by_user",
                    }
                )
                self.db.update_progress(status="stopped", completed=completed)
                return sweep_id

            run_key = make_run_key(config_hash, model_cfg.id, strategy_id, task.id, budget, seed)
            if resume and self.db.run_exists(run_key):
                completed += 1
                self.db.update_progress(completed=completed, total=total)
                continue

            self.db.update_progress(
                current_model=model_cfg.id,
                current_strategy=strategy_id,
                current_task=task.id,
                current_budget=budget,
                completed=completed,
                total=total,
            )

            try:
                result_row = self._execute_one(
                    sweep_id=sweep_id,
                    config_hash=config_hash,
                    run_key=run_key,
                    model_cfg=model_cfg,
                    strategy_id=strategy_id,
                    task=task,
                    budget=budget,
                    seed=seed,
                    temperature=temperature,
                    phase=phase,
                )
                self.db.insert_run(result_row)
                ok = "OK" if result_row["correct"] else "FAIL"
                self.db.append_log(
                    f"{ok} {model_cfg.id}/{strategy_id}/{task.id}/B={budget}/seed={seed} "
                    f"tokens={result_row['tokens_spent']}"
                )
            except Exception as e:
                self.db.append_log(f"ERROR {strategy_id}/{task.id}: {e}")
                self.db.insert_run(
                    {
                        "id": str(uuid.uuid4()),
                        "run_key": run_key,
                        "sweep_id": sweep_id,
                        "phase": phase,
                        "model": model_cfg.id,
                        "strategy": strategy_id,
                        "task_id": task.id,
                        "budget": budget,
                        "seed": seed,
                        "correct": None,
                        "final_answer": None,
                        "expected_answer": task.answer,
                        "tokens_spent": None,
                        "prompt_tokens_spent": None,
                        "target_budget": budget,
                        "overshoot_flagged": 0,
                        "budget_exhausted": 0,
                        "truncated_any": 0,
                        "tool_calls": 0,
                        "estimated_cost": 0.0,
                        "transcript_json": "[]",
                        "metadata_json": json.dumps({"traceback": traceback.format_exc()}),
                        "error": str(e),
                        "created_at": time.time(),
                        "duration_s": None,
                    }
                )

            completed += 1
            self.db.upsert_sweep(
                {
                    "id": sweep_id,
                    "config_hash": config_hash,
                    "phase": phase,
                    "status": "running",
                    "config_json": json.dumps(config),
                    "total_runs": total,
                    "completed_runs": completed,
                    "created_at": time.time(),
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                }
            )
            self.db.update_progress(completed=completed, total=total)

        self.db.upsert_sweep(
            {
                "id": sweep_id,
                "config_hash": config_hash,
                "phase": phase,
                "status": "completed",
                "config_json": json.dumps(config),
                "total_runs": total,
                "completed_runs": completed,
                "created_at": time.time(),
                "started_at": None,
                "finished_at": time.time(),
                "error": None,
            }
        )
        self.db.update_progress(status="completed", completed=completed, total=total)
        self.db.append_log(f"Sweep {sweep_id} completed: {completed}/{total}")
        return sweep_id

    def _execute_one(
        self,
        *,
        sweep_id: str,
        config_hash: str,
        run_key: str,
        model_cfg: Any,
        strategy_id: str,
        task: Task,
        budget: int,
        seed: int,
        temperature: float,
        phase: str,
    ) -> dict[str, Any]:
        t0 = time.time()
        adapter = ModelAdapter(model_cfg, temperature=temperature)
        strategy = build_strategy(strategy_id, phase=phase, budget=budget)
        result = strategy.run(task, adapter, budget)
        grade_result = grade(task.grader, result.final_answer, task.answer, task.grader_params)
        cost = adapter.estimate_cost(result.prompt_tokens_spent, result.tokens_spent)
        truncated_any = any(t.truncated for t in result.transcript)
        tool_calls = sum(1 for t in result.transcript if t.role == "tool_call")
        meta = {
            **result.metadata,
            "grade": grade_result,
            "config_hash": config_hash,
            "seed": seed,
        }
        return {
            "id": str(uuid.uuid4()),
            "run_key": run_key,
            "sweep_id": sweep_id,
            "phase": phase,
            "model": model_cfg.id,
            "strategy": strategy_id,
            "task_id": task.id,
            "budget": budget,
            "seed": seed,
            "correct": 1 if grade_result.get("correct") else 0,
            "final_answer": result.final_answer,
            "expected_answer": task.answer,
            "tokens_spent": result.tokens_spent,
            "prompt_tokens_spent": result.prompt_tokens_spent,
            "target_budget": budget,
            "overshoot_flagged": 1 if result.overshoot_flagged else 0,
            "budget_exhausted": 1 if result.budget_exhausted else 0,
            "truncated_any": 1 if truncated_any else 0,
            "tool_calls": tool_calls,
            "estimated_cost": cost,
            "transcript_json": json.dumps([t.to_dict() for t in result.transcript]),
            "metadata_json": json.dumps(meta, default=str),
            "error": None,
            "created_at": time.time(),
            "duration_s": time.time() - t0,
        }


# Module-level runner for API stop control
_active_runner: SweepRunner | None = None


def get_active_runner() -> SweepRunner | None:
    return _active_runner


def set_active_runner(runner: SweepRunner | None) -> None:
    global _active_runner
    _active_runner = runner
