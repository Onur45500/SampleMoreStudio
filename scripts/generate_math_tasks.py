#!/usr/bin/env python3
"""Generate Phase 1 math tasks from offline GSM8K slice → Hub → seed fallback."""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tasks" / "phase1_reasoning" / "math"
OFFLINE = ROOT / "tasks" / "sources" / "gsm8k_slice.jsonl"

SEED_TASKS = [
    ("Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?", "72"),
    ("Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?", "10"),
    ("Betty is saving money for a new wallet which costs $100. Betty has only half of the money she needs. Her parents decided to give her $15 for that purpose, and her grandparents twice as much as her parents. How much more money does Betty need to buy the wallet?", "5"),
]


def extract_gsm8k_answer(raw: str) -> str:
    if "####" in raw:
        return raw.split("####")[-1].strip().replace(",", "")
    return raw.strip()


def load_offline_slice() -> list[tuple[str, str, str]]:
    if not OFFLINE.exists():
        return []
    out: list[tuple[str, str, str]] = []
    for line in OFFLINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        q = str(row["question"]).strip()
        a = extract_gsm8k_answer(str(row["answer"]))
        out.append((q, a, "gsm8k_offline"))
    return out


def write_task(idx: int, prompt: str, answer: str, source: str) -> None:
    tid = f"math_{idx:03d}"
    data = {
        "id": tid,
        "category": "math",
        "prompt": prompt,
        "answer": answer,
        "grader": "numeric_tolerance",
        "grader_params": {"tolerance": 0.01},
        "metadata": {"source": source},
    }
    (OUT / f"{tid}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def main(n: int = 50) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.json"):
        p.unlink()

    tasks: list[tuple[str, str, str]] = []

    # 1) Prefer checked-in offline GSM8K slice (no Hub/SSL required)
    offline = load_offline_slice()
    if offline:
        tasks.extend(offline)
        print(f"Loaded {len(offline)} tasks from {OFFLINE}")

    # 2) Optionally top up from Hub if still short
    if len(tasks) < n:
        try:
            from datasets import load_dataset

            ds = load_dataset("gsm8k", "main", split="test")
            rng = random.Random(42)
            indices = list(range(len(ds)))
            rng.shuffle(indices)
            for i in indices:
                if len(tasks) >= n:
                    break
                row = ds[i]
                q = row["question"].strip()
                a = extract_gsm8k_answer(row["answer"])
                if any(q[:40] == t[0][:40] for t in tasks):
                    continue
                tasks.append((q, a, "gsm8k_hub"))
            print(f"After Hub top-up: {len(tasks)} tasks")
        except Exception as e:
            print(f"Hub unavailable ({e}); continuing with offline/seed")

    # 3) Seed + synthetic fallback
    if len(tasks) < n:
        for q, a in SEED_TASKS:
            if any(q[:40] == t[0][:40] for t in tasks):
                continue
            tasks.append((q, a, "seed"))
        rng = random.Random(42)
        while len(tasks) < n:
            a, b = rng.randint(2, 40), rng.randint(2, 40)
            op = rng.choice(["+", "-", "*"])
            if op == "+":
                ans, q = a + b, f"What is {a} plus {b}?"
            elif op == "-":
                if b > a:
                    a, b = b, a
                ans, q = a - b, f"What is {a} minus {b}?"
            else:
                ans, q = a * b, f"What is {a} times {b}?"
            tasks.append((q, str(ans), "synthetic"))

    tasks = tasks[:n]
    for i, (q, a, src) in enumerate(tasks, start=1):
        write_task(i, q, a, src)
    print(f"Wrote {len(tasks)} math tasks to {OUT}")
    sources = {}
    for _, _, s in tasks:
        sources[s] = sources.get(s, 0) + 1
    print(f"Sources: {sources}")


if __name__ == "__main__":
    main()
