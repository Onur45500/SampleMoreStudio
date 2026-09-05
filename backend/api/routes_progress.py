"""Sweep control and progress polling."""
from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import get_db
from backend.sweep_runner import SweepRunner, get_active_runner, set_active_runner

router = APIRouter(prefix="/api", tags=["sweeps"])


class SweepStartBody(BaseModel):
    phase: str = "phase1_reasoning"
    models: list[str] | None = None
    strategies: list[str] | None = None
    budgets: list[int] | None = None
    n_seeds: int | None = None
    task_limit: int | None = None
    categories: list[str] | None = None
    resume: bool = True
    preset: str | None = None


def _load_preset(name: str) -> dict[str, Any]:
    from backend.config_loader import load_yaml

    cfg = load_yaml("sweeps.yaml")
    presets = cfg.get("presets", cfg)
    if name not in presets:
        raise HTTPException(404, f"Unknown preset: {name}")
    return dict(presets[name])


def _resolve_body(body: SweepStartBody) -> dict[str, Any]:
    if body.preset:
        p = _load_preset(body.preset)
        return {
            "phase": p.get("phase", body.phase),
            "models": body.models or p.get("models"),
            "strategies": body.strategies or p.get("strategies"),
            "budgets": body.budgets or p.get("budgets"),
            "n_seeds": body.n_seeds if body.n_seeds is not None else p.get("n_seeds"),
            "task_limit": body.task_limit if body.task_limit is not None else p.get("task_limit"),
            "categories": body.categories if body.categories is not None else p.get("categories"),
            "resume": body.resume,
        }
    return {
        "phase": body.phase,
        "models": body.models,
        "strategies": body.strategies,
        "budgets": body.budgets,
        "n_seeds": body.n_seeds,
        "task_limit": body.task_limit,
        "categories": body.categories,
        "resume": body.resume,
    }


@router.post("/sweeps/start")
def start_sweep(body: SweepStartBody) -> dict[str, Any]:
    active = get_active_runner()
    prog = get_db().get_progress()
    if active and prog.get("status") == "running":
        raise HTTPException(409, "A sweep is already running")

    params = _resolve_body(body)
    runner = SweepRunner()
    set_active_runner(runner)

    def _job() -> None:
        try:
            runner.run_sweep(**params)
        finally:
            set_active_runner(None)

    t = threading.Thread(target=_job, daemon=True)
    t.start()
    return {"data": {"status": "started", "params": params, "preset": body.preset}, "error": None}


@router.post("/sweeps/{sweep_id}/stop")
def stop_sweep(sweep_id: str) -> dict[str, Any]:
    active = get_active_runner()
    if active:
        active.request_stop()
        return {"data": {"status": "stop_requested", "sweep_id": sweep_id}, "error": None}
    get_db().update_progress(status="stopped")
    return {"data": {"status": "idle"}, "error": None}


@router.get("/sweeps")
def list_sweeps() -> dict[str, Any]:
    return {"data": get_db().list_sweeps(), "error": None}


@router.get("/progress")
def progress() -> dict[str, Any]:
    data = get_db().get_progress()
    # Rough ETA from elapsed rate
    completed = int(data.get("completed") or 0)
    total = int(data.get("total") or 0)
    updated = float(data.get("updated_at") or 0)
    started = updated
    sweeps = get_db().list_sweeps()
    if sweeps and data.get("sweep_id"):
        for s in sweeps:
            if s["id"] == data.get("sweep_id") and s.get("started_at"):
                started = float(s["started_at"])
                break
    eta_s = None
    if completed > 0 and total > completed and started:
        import time

        elapsed = max(1.0, time.time() - started)
        rate = completed / elapsed
        eta_s = (total - completed) / rate if rate > 0 else None
    data["eta_seconds"] = eta_s
    return {"data": data, "error": None}
