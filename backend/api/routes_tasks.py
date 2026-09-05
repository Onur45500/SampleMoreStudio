"""Task browser routes."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.config_loader import load_tasks
from backend.db import get_db

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/tasks")
def list_tasks(phase: str | None = None) -> dict[str, Any]:
    tasks = load_tasks(phase=phase)
    # Attach pass rates
    runs = get_db().query_runs(phase=phase, limit=100000)
    by_task: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        if r.get("correct") is not None and not r.get("error"):
            by_task[r["task_id"]].append(float(r["correct"]))
    data = []
    for t in tasks:
        rates = by_task.get(t.id, [])
        data.append(
            {
                **t.to_dict(),
                "pass_rate": sum(rates) / len(rates) if rates else None,
                "n_runs": len(rates),
            }
        )
    return {"data": data, "error": None}


@router.get("/tasks/{task_id}/results")
def task_results(task_id: str) -> dict[str, Any]:
    tasks = {t.id: t for t in load_tasks()}
    if task_id not in tasks:
        raise HTTPException(404, "task not found")
    rows = get_db().query_runs(task_id=task_id, limit=5000)
    for r in rows:
        r.pop("transcript_json", None)
    return {"data": {"task": tasks[task_id].to_dict(), "runs": rows}, "error": None}
