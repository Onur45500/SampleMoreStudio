#!/usr/bin/env python3
"""Generate Phase 2 tool-use tasks (file / json / calc) with known ground truth."""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tasks" / "phase2_agent"


def write(category: str, tid: str, data: dict) -> None:
    out = BASE / category
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{tid}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def gen_file_tasks(n: int = 12) -> None:
    rng = random.Random(11)
    cities = ["Paris", "Tokyo", "Cairo", "Lima", "Oslo", "Berlin", "Seoul", "Nairobi"]
    for i in range(1, n + 1):
        city = cities[i % len(cities)]
        pop = rng.randint(100, 999) * 1000
        year = 2000 + rng.randint(0, 24)
        files = {
            "notes/readme.txt": f"Capital data for region {i}",
            f"notes/city_{i}.txt": f"City: {city}\nPopulation: {pop}\nFounded: {year}",
            "notes/misc.txt": "ignore me",
        }
        tid = f"file_{i:03d}"
        write(
            "file_tools",
            tid,
            {
                "id": tid,
                "category": "file_tools",
                "prompt": (
                    f"Using the file tools, find the population of the city described in notes/city_{i}.txt. "
                    "Report only the population number."
                ),
                "answer": str(pop),
                "grader": "tool_answer",
                "grader_params": {"domain": "math", "tolerance": 0},
                "metadata": {"tool_kind": "file", "files": files, "source": "generated"},
            },
        )


def gen_json_tasks(n: int = 12) -> None:
    rng = random.Random(22)
    for i in range(1, n + 1):
        users = [
            {"name": f"user{j}", "score": rng.randint(1, 100), "active": j % 2 == 0}
            for j in range(5)
        ]
        target = users[i % 5]
        tid = f"json_{i:03d}"
        write(
            "json_tools",
            tid,
            {
                "id": tid,
                "category": "json_tools",
                "prompt": (
                    f"Using json tools, what is the score of {target['name']}? "
                    "The data is available via json_get / json_keys on the root object with key 'users'."
                ),
                "answer": str(target["score"]),
                "grader": "tool_answer",
                "grader_params": {"domain": "math", "tolerance": 0},
                "metadata": {
                    "tool_kind": "json",
                    "data": {"users": users, "meta": {"version": 1}},
                    "source": "generated",
                },
            },
        )


def gen_calc_tasks(n: int = 12) -> None:
    rng = random.Random(33)
    for i in range(1, n + 1):
        a, b, c = rng.randint(2, 20), rng.randint(2, 20), rng.randint(2, 9)
        # (a + b) * c
        ans = (a + b) * c
        tid = f"calc_{i:03d}"
        write(
            "calc_tools",
            tid,
            {
                "id": tid,
                "category": "calc_tools",
                "prompt": (
                    f"Use the calculator tool to compute ({a} + {b}) * {c}. "
                    "You must use the tool; do not compute only in your head."
                ),
                "answer": str(ans),
                "grader": "tool_answer",
                "grader_params": {"domain": "math", "tolerance": 1e-6},
                "metadata": {"tool_kind": "calc", "source": "generated"},
            },
        )


def main() -> None:
    for sub in ("file_tools", "json_tools", "calc_tools"):
        d = BASE / sub
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*.json"):
            p.unlink()
    gen_file_tasks()
    gen_json_tasks()
    gen_calc_tasks()
    print("Wrote Phase 2 tool tasks")


if __name__ == "__main__":
    main()
