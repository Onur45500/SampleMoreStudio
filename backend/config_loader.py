"""Load YAML configs and task JSON files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from backend.types import ModelConfig, Task

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
TASKS = ROOT / "tasks"


def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_models(enabled_only: bool = True) -> list[ModelConfig]:
    raw = load_yaml("models.yaml")
    models = []
    for m in raw.get("models", []):
        cfg = ModelConfig(
            id=m["id"],
            litellm_model=m["litellm_model"],
            provider=m.get("provider", "unknown"),
            local=bool(m.get("local", False)),
            cost_per_1k_completion=float(m.get("cost_per_1k_completion", 0)),
            cost_per_1k_prompt=float(m.get("cost_per_1k_prompt", 0)),
            enabled=bool(m.get("enabled", True)),
            notes=m.get("notes", ""),
        )
        if enabled_only and not cfg.enabled:
            continue
        models.append(cfg)
    return models


def load_budget_config() -> dict[str, Any]:
    return load_yaml("budgets.yaml")


def load_strategies_config() -> dict[str, Any]:
    return load_yaml("strategies.yaml")


def load_temperature() -> float:
    raw = load_yaml("models.yaml")
    return float(raw.get("default_temperature", 0.7))


def _load_task_file(path: Path, phase: str, category: str) -> Task:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Task(
        id=data["id"],
        phase=phase,  # type: ignore[arg-type]
        category=data.get("category", category),
        prompt=data["prompt"],
        answer=str(data["answer"]),
        grader=data.get("grader", "exact_match"),
        grader_params=data.get("grader_params", {}),
        metadata=data.get("metadata", {}),
    )


def load_tasks(
    phase: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> list[Task]:
    tasks: list[Task] = []
    roots = []
    if phase in (None, "phase1_reasoning"):
        roots.append(("phase1_reasoning", TASKS / "phase1_reasoning"))
    if phase in (None, "phase2_agent"):
        roots.append(("phase2_agent", TASKS / "phase2_agent"))

    for phase_name, root in roots:
        if not root.exists():
            continue
        for cat_dir in sorted(root.iterdir()):
            if not cat_dir.is_dir():
                continue
            cat = cat_dir.name
            if category and cat != category and category not in cat:
                continue
            for fp in sorted(cat_dir.glob("*.json")):
                tasks.append(_load_task_file(fp, phase_name, cat))

    if limit is not None:
        tasks = tasks[:limit]
    return tasks


def get_model(model_id: str) -> ModelConfig:
    for m in load_models(enabled_only=False):
        if m.id == model_id:
            return m
    raise KeyError(f"Unknown model: {model_id}")
