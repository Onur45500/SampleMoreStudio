#!/usr/bin/env python3
"""Hand-authored small code completion tasks with unit-test graders."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tasks" / "phase1_reasoning" / "code"

TASKS = [
    {
        "id": "code_001",
        "prompt": "Write a Python function `add(a, b)` that returns the sum of a and b.",
        "tests": "assert add(2, 3) == 5\nassert add(-1, 1) == 0",
    },
    {
        "id": "code_002",
        "prompt": "Write a Python function `is_even(n)` that returns True if n is even else False.",
        "tests": "assert is_even(2) is True\nassert is_even(3) is False",
    },
    {
        "id": "code_003",
        "prompt": "Write a Python function `factorial(n)` that returns n! for n >= 0.",
        "tests": "assert factorial(0) == 1\nassert factorial(5) == 120",
    },
    {
        "id": "code_004",
        "prompt": "Write a Python function `reverse_string(s)` that returns the reversed string.",
        "tests": "assert reverse_string('abc') == 'cba'\nassert reverse_string('') == ''",
    },
    {
        "id": "code_005",
        "prompt": "Write a Python function `max_of_three(a, b, c)` returning the maximum of three numbers.",
        "tests": "assert max_of_three(1, 5, 3) == 5\nassert max_of_three(-1, -5, -3) == -1",
    },
    {
        "id": "code_006",
        "prompt": "Write a Python function `count_vowels(s)` that counts vowels aeiou (case-insensitive).",
        "tests": "assert count_vowels('Hello') == 2\nassert count_vowels('xyz') == 0",
    },
    {
        "id": "code_007",
        "prompt": "Write a Python function `fibonacci(n)` returning the n-th Fibonacci number with fib(0)=0, fib(1)=1.",
        "tests": "assert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(10) == 55",
    },
    {
        "id": "code_008",
        "prompt": "Write a Python function `is_palindrome(s)` ignoring spaces and case.",
        "tests": "assert is_palindrome('Race car') is True\nassert is_palindrome('hello') is False",
    },
    {
        "id": "code_009",
        "prompt": "Write a Python function `unique_list(xs)` that returns a new list with duplicates removed preserving order.",
        "tests": "assert unique_list([1,2,2,3,1]) == [1,2,3]",
    },
    {
        "id": "code_010",
        "prompt": "Write a Python function `sum_list(xs)` that returns the sum of numbers in xs.",
        "tests": "assert sum_list([1,2,3]) == 6\nassert sum_list([]) == 0",
    },
    {
        "id": "code_011",
        "prompt": "Write a Python function `gcd(a, b)` returning the greatest common divisor.",
        "tests": "assert gcd(12, 8) == 4\nassert gcd(7, 3) == 1",
    },
    {
        "id": "code_012",
        "prompt": "Write a Python function `flatten(xss)` that flattens one level of nested lists.",
        "tests": "assert flatten([[1,2],[3],[]]) == [1,2,3]",
    },
    {
        "id": "code_013",
        "prompt": "Write a Python function `word_count(s)` returning the number of whitespace-separated words.",
        "tests": "assert word_count('hello world') == 2\nassert word_count('  a  b ') == 2",
    },
    {
        "id": "code_014",
        "prompt": "Write a Python function `clamp(x, lo, hi)` that clamps x into [lo, hi].",
        "tests": "assert clamp(5, 0, 10) == 5\nassert clamp(-1, 0, 10) == 0\nassert clamp(99, 0, 10) == 10",
    },
    {
        "id": "code_015",
        "prompt": "Write a Python function `median(xs)` for a non-empty list of numbers (sort and pick middle / average of two middles).",
        "tests": "assert median([1,3,2]) == 2\nassert median([1,2,3,4]) == 2.5",
    },
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.json"):
        p.unlink()
    for t in TASKS:
        data = {
            "id": t["id"],
            "category": "code",
            "prompt": t["prompt"]
            + "\n\nReturn only the function implementation in a python code block. End with Answer: done",
            "answer": "tests_pass",
            "grader": "code_tests",
            "grader_params": {"tests": t["tests"], "timeout": 5},
            "metadata": {"source": "handwritten"},
        }
        (OUT / f"{t['id']}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(TASKS)} code tasks")


if __name__ == "__main__":
    main()
