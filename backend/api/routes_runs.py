"""Run list/detail routes."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.db import get_db

router = APIRouter(prefix="/api", tags=["runs"])


def _parse_run(row: dict[str, Any], include_transcript: bool = False) -> dict[str, Any]:
    out = dict(row)
    if not include_transcript:
        out.pop("transcript_json", None)
    else:
        try:
            out["transcript"] = json.loads(out.get("transcript_json") or "[]")
        except json.JSONDecodeError:
            out["transcript"] = []
    if out.get("metadata_json"):
        try:
            out["metadata"] = json.loads(out["metadata_json"])
        except json.JSONDecodeError:
            out["metadata"] = {}
    return out


@router.get("/runs")
def list_runs(
    phase: str | None = None,
    model: str | None = None,
    strategy: str | None = None,
    task: str | None = None,
    budget: int | None = None,
    correct: bool | None = None,
    sweep_id: str | None = None,
    limit: int = Query(200, le=5000),
    offset: int = 0,
) -> dict[str, Any]:
    rows = get_db().query_runs(
        phase=phase,
        model=model,
        strategy=strategy,
        task_id=task,
        budget=budget,
        correct=correct,
        sweep_id=sweep_id,
        limit=limit,
        offset=offset,
    )
    return {"data": [_parse_run(r) for r in rows], "error": None}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    row = get_db().get_run(run_id)
    if not row:
        raise HTTPException(404, "run not found")
    return {"data": _parse_run(row, include_transcript=True), "error": None}


@router.get("/runs/{run_id}/transcript")
def get_transcript(run_id: str) -> dict[str, Any]:
    row = get_db().get_run(run_id)
    if not row:
        raise HTTPException(404, "run not found")
    try:
        transcript = json.loads(row.get("transcript_json") or "[]")
    except json.JSONDecodeError:
        transcript = []
    return {
        "data": {
            "run_id": run_id,
            "transcript": transcript,
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
        },
        "error": None,
    }
