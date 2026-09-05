"""FastAPI application entrypoint."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_leaderboard import router as leaderboard_router
from backend.api.routes_progress import router as progress_router
from backend.api.routes_runs import router as runs_router
from backend.api.routes_tasks import router as tasks_router
from backend.db import get_db

app = FastAPI(title="SampleMoreStudio", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leaderboard_router)
app.include_router(runs_router)
app.include_router(tasks_router)
app.include_router(progress_router)


@app.on_event("startup")
def startup() -> None:
    get_db()


@app.get("/api/health")
def health():
    return {"data": {"ok": True, "version": "0.2.0"}, "error": None}
