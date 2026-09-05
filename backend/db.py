"""SQLite storage for runs, sweeps, and transcripts."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "results" / "studio.db"

_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS sweeps (
    id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    config_json TEXT NOT NULL,
    total_runs INTEGER NOT NULL DEFAULT 0,
    completed_runs INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    sweep_id TEXT,
    phase TEXT NOT NULL,
    model TEXT NOT NULL,
    strategy TEXT NOT NULL,
    task_id TEXT NOT NULL,
    budget INTEGER NOT NULL,
    seed INTEGER NOT NULL DEFAULT 0,
    correct INTEGER,
    final_answer TEXT,
    expected_answer TEXT,
    tokens_spent INTEGER,
    prompt_tokens_spent INTEGER,
    target_budget INTEGER,
    overshoot_flagged INTEGER DEFAULT 0,
    budget_exhausted INTEGER DEFAULT 0,
    truncated_any INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0.0,
    transcript_json TEXT,
    metadata_json TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    duration_s REAL,
    FOREIGN KEY (sweep_id) REFERENCES sweeps(id)
);

CREATE INDEX IF NOT EXISTS idx_runs_sweep ON runs(sweep_id);
CREATE INDEX IF NOT EXISTS idx_runs_filters ON runs(phase, model, strategy, budget);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_key ON runs(run_key);

CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sweep_id TEXT,
    status TEXT,
    current_model TEXT,
    current_strategy TEXT,
    current_task TEXT,
    current_budget INTEGER,
    completed INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    log_tail TEXT DEFAULT '[]',
    updated_at REAL
);
"""


class Database:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DEFAULT_DB
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        with _lock:
            c = self._connect()
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()

    def _init(self) -> None:
        with self.conn() as c:
            c.executescript(SCHEMA)
            c.execute(
                "INSERT OR IGNORE INTO progress (id, status, completed, total, log_tail, updated_at) "
                "VALUES (1, 'idle', 0, 0, '[]', ?)",
                (time.time(),),
            )

    def upsert_sweep(self, sweep: dict[str, Any]) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO sweeps (id, config_hash, phase, status, config_json, total_runs,
                                    completed_runs, created_at, started_at, finished_at, error)
                VALUES (:id, :config_hash, :phase, :status, :config_json, :total_runs,
                        :completed_runs, :created_at, :started_at, :finished_at, :error)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    completed_runs=excluded.completed_runs,
                    started_at=COALESCE(excluded.started_at, sweeps.started_at),
                    finished_at=excluded.finished_at,
                    error=excluded.error
                """,
                sweep,
            )

    def get_sweep(self, sweep_id: str) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM sweeps WHERE id=?", (sweep_id,)).fetchone()
            return dict(row) if row else None

    def list_sweeps(self) -> list[dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM sweeps ORDER BY created_at DESC")]

    def run_exists(self, run_key: str) -> bool:
        with self.conn() as c:
            row = c.execute(
                "SELECT 1 FROM runs WHERE run_key=? AND error IS NULL AND correct IS NOT NULL",
                (run_key,),
            ).fetchone()
            return row is not None

    def insert_run(self, run: dict[str, Any]) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO runs (
                    id, run_key, sweep_id, phase, model, strategy, task_id, budget, seed,
                    correct, final_answer, expected_answer, tokens_spent, prompt_tokens_spent,
                    target_budget, overshoot_flagged, budget_exhausted, truncated_any,
                    tool_calls, estimated_cost, transcript_json, metadata_json, error,
                    created_at, duration_s
                ) VALUES (
                    :id, :run_key, :sweep_id, :phase, :model, :strategy, :task_id, :budget, :seed,
                    :correct, :final_answer, :expected_answer, :tokens_spent, :prompt_tokens_spent,
                    :target_budget, :overshoot_flagged, :budget_exhausted, :truncated_any,
                    :tool_calls, :estimated_cost, :transcript_json, :metadata_json, :error,
                    :created_at, :duration_s
                )
                ON CONFLICT(run_key) DO UPDATE SET
                    correct=excluded.correct,
                    final_answer=excluded.final_answer,
                    tokens_spent=excluded.tokens_spent,
                    prompt_tokens_spent=excluded.prompt_tokens_spent,
                    overshoot_flagged=excluded.overshoot_flagged,
                    budget_exhausted=excluded.budget_exhausted,
                    truncated_any=excluded.truncated_any,
                    tool_calls=excluded.tool_calls,
                    estimated_cost=excluded.estimated_cost,
                    transcript_json=excluded.transcript_json,
                    metadata_json=excluded.metadata_json,
                    error=excluded.error,
                    duration_s=excluded.duration_s,
                    created_at=excluded.created_at
                """,
                run,
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            return dict(row) if row else None

    def get_run_by_key(self, run_key: str) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM runs WHERE run_key=?", (run_key,)).fetchone()
            return dict(row) if row else None

    def query_runs(
        self,
        phase: str | None = None,
        model: str | None = None,
        strategy: str | None = None,
        task_id: str | None = None,
        budget: int | None = None,
        correct: bool | None = None,
        sweep_id: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in [
            ("phase", phase),
            ("model", model),
            ("strategy", strategy),
            ("task_id", task_id),
            ("budget", budget),
            ("sweep_id", sweep_id),
        ]:
            if val is not None:
                clauses.append(f"{col}=?")
                params.append(val)
        if correct is not None:
            clauses.append("correct=?")
            params.append(1 if correct else 0)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM runs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, params)]

    def leaderboard(
        self,
        phase: str | None = None,
        model: str | None = None,
        strategy: str | None = None,
        budget: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["correct IS NOT NULL", "error IS NULL"]
        params: list[Any] = []
        for col, val in [("phase", phase), ("model", model), ("strategy", strategy), ("budget", budget)]:
            if val is not None:
                clauses.append(f"{col}=?")
                params.append(val)
        where = " WHERE " + " AND ".join(clauses)
        sql = f"""
            SELECT phase, model, strategy, budget,
                   AVG(correct) AS accuracy,
                   COUNT(*) AS n_runs,
                   AVG(tokens_spent) AS avg_tokens_spent,
                   AVG(target_budget) AS avg_target_budget,
                   AVG(prompt_tokens_spent) AS avg_prompt_tokens,
                   AVG(tool_calls) AS avg_tool_calls,
                   AVG(estimated_cost) AS avg_cost,
                   SUM(overshoot_flagged) AS n_overshoot,
                   SUM(budget_exhausted) AS n_budget_exhausted,
                   AVG(CAST(truncated_any AS REAL)) AS truncation_rate
            FROM runs
            {where}
            GROUP BY phase, model, strategy, budget
            ORDER BY accuracy DESC, model, strategy, budget
        """
        with self.conn() as c:
            rows = [dict(r) for r in c.execute(sql, params)]
        for r in rows:
            r["truncation_rate"] = float(r.get("truncation_rate") or 0)
        return rows

    def update_progress(self, **kwargs: Any) -> None:
        allowed = {
            "sweep_id", "status", "current_model", "current_strategy", "current_task",
            "current_budget", "completed", "total", "log_tail", "updated_at",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if "updated_at" not in fields:
            fields["updated_at"] = time.time()
        if "log_tail" in fields and not isinstance(fields["log_tail"], str):
            fields["log_tail"] = json.dumps(fields["log_tail"][-200:])
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE progress SET {sets} WHERE id=1", list(fields.values()))

    def get_progress(self) -> dict[str, Any]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM progress WHERE id=1").fetchone()
            d = dict(row) if row else {}
            if "log_tail" in d and isinstance(d["log_tail"], str):
                try:
                    d["log_tail"] = json.loads(d["log_tail"])
                except json.JSONDecodeError:
                    d["log_tail"] = []
            return d

    def cost_summary(self) -> dict[str, Any]:
        with self.conn() as c:
            row = c.execute(
                """
                SELECT COUNT(*) AS n_runs,
                       COALESCE(SUM(tokens_spent),0) AS total_completion_tokens,
                       COALESCE(SUM(prompt_tokens_spent),0) AS total_prompt_tokens,
                       COALESCE(SUM(estimated_cost),0) AS total_cost,
                       SUM(CASE WHEN estimated_cost=0 THEN 1 ELSE 0 END) AS local_runs,
                       SUM(CASE WHEN estimated_cost>0 THEN 1 ELSE 0 END) AS api_runs
                FROM runs WHERE error IS NULL
                """
            ).fetchone()
            return dict(row) if row else {}

    def append_log(self, message: str) -> None:
        prog = self.get_progress()
        logs = prog.get("log_tail") or []
        if isinstance(logs, str):
            try:
                logs = json.loads(logs)
            except json.JSONDecodeError:
                logs = []
        logs.append({"ts": time.time(), "msg": message})
        self.update_progress(log_tail=logs[-200:])


_db: Database | None = None


def get_db(path: Path | str | None = None) -> Database:
    global _db
    if _db is None or (path and Path(path) != _db.path):
        _db = Database(path)
    return _db
