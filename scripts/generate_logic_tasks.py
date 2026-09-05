#!/usr/bin/env python3
"""Programmatically generate logic puzzles with known answers."""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tasks" / "phase1_reasoning" / "logic"


def main(n: int = 20) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.json"):
        p.unlink()
    rng = random.Random(7)
    tasks = []

    # Syllogism / set membership
    for i in range(5):
        a, b, c = rng.sample(["A", "B", "C", "D", "E"], 3)
        ans = "yes"
        q = (
            f"All {a}s are {b}s. All {b}s are {c}s. Is every {a} a {c}? "
            f"Answer yes or no."
        )
        tasks.append((q, ans, "exact_match"))

    for i in range(3):
        a, b = rng.sample(["cats", "dogs", "birds", "fish"], 2)
        q = (
            f"Some {a} are pets. No pets are wild. Can we conclude that some {a} are wild? "
            f"Answer yes or no."
        )
        tasks.append((q, "no", "exact_match"))

    # Number sequences
    for _ in range(5):
        start = rng.randint(1, 10)
        step = rng.randint(2, 5)
        seq = [start + i * step for i in range(4)]
        nxt = start + 4 * step
        q = f"What is the next number in the sequence: {', '.join(map(str, seq))}?"
        tasks.append((q, str(nxt), "numeric_tolerance"))

    # Truth / knights
    tasks.append(
        (
            "There are two types of people: knights always tell the truth, knaves always lie. "
            "A says: 'B is a knight.' B says: 'A and I are of opposite types.' What is A? "
            "Answer knight or knave.",
            "knave",
            "exact_match",
        )
    )
    tasks.append(
        (
            "If today is Monday, tomorrow is Tuesday. Today is Monday. What day is tomorrow? "
            "Answer with the weekday name.",
            "tuesday",
            "exact_match",
        )
    )

    # Comparisons
    for _ in range(4):
        x, y, z = rng.sample(range(1, 20), 3)
        q = f"Among {x}, {y}, and {z}, which is the largest?"
        tasks.append((q, str(max(x, y, z)), "numeric_tolerance"))

    # Parity
    for _ in range(2):
        n_val = rng.randint(10, 99)
        q = f"Is {n_val} even or odd?"
        tasks.append((q, "even" if n_val % 2 == 0 else "odd", "exact_match"))

    tasks = tasks[:n]
    for i, (prompt, answer, grader) in enumerate(tasks, start=1):
        tid = f"logic_{i:03d}"
        params = {"domain": "logic"}
        if grader == "numeric_tolerance":
            params = {"tolerance": 0.01}
        data = {
            "id": tid,
            "category": "logic",
            "prompt": prompt,
            "answer": answer,
            "grader": grader,
            "grader_params": params,
            "metadata": {"source": "generated"},
        }
        (OUT / f"{tid}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(tasks)} logic tasks")


if __name__ == "__main__":
    main()
