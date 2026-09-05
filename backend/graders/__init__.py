"""Deterministic graders — no LLM judges."""
from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from backend.answer_extraction import answers_equal, extract_answer, normalize_answer


def grade(task_grader: str, predicted: str, expected: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    graders = {
        "numeric_tolerance": grade_numeric,
        "exact_match": grade_exact,
        "regex": grade_regex,
        "code_tests": grade_code,
        "tool_answer": grade_tool_answer,
    }
    fn = graders.get(task_grader, grade_exact)
    return fn(predicted, expected, params)


def grade_numeric(predicted: str, expected: str, params: dict[str, Any]) -> dict[str, Any]:
    tol = float(params.get("tolerance", 1e-3))
    pred = extract_answer(predicted, "math") if "Answer:" not in predicted[:20] else normalize_answer(predicted, "math")
    # predicted may already be extracted
    pred = normalize_answer(predicted, "math")
    exp = normalize_answer(expected, "math")
    ok = answers_equal(pred, exp, "math", tol)
    return {"correct": ok, "predicted": pred, "expected": exp, "grader": "numeric_tolerance"}


def grade_exact(predicted: str, expected: str, params: dict[str, Any]) -> dict[str, Any]:
    domain = params.get("domain", "logic")
    pred = normalize_answer(predicted, domain)
    exp = normalize_answer(expected, domain)
    ok = pred == exp
    return {"correct": ok, "predicted": pred, "expected": exp, "grader": "exact_match"}


def grade_regex(predicted: str, expected: str, params: dict[str, Any]) -> dict[str, Any]:
    pattern = params.get("pattern") or expected
    flags = re.IGNORECASE if params.get("ignore_case", True) else 0
    ok = bool(re.search(pattern, predicted, flags))
    return {"correct": ok, "predicted": predicted.strip(), "expected": pattern, "grader": "regex"}


def grade_code(predicted: str, expected: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run sandboxed unit tests via subprocess (NOT a security boundary)."""
    timeout = float(params.get("timeout", 5.0))
    tests = params.get("tests") or expected
    # Extract python code from fences if present
    code = predicted
    fence = re.search(r"```(?:python)?\n(.*?)```", predicted, re.DOTALL)
    if fence:
        code = fence.group(1)
    # Also try Answer: block
    if "def " not in code:
        code = predicted

    script = textwrap.dedent(
        f"""
        import sys
        {code}
        
        {tests}
        print("OK")
        """
    )
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "solution.py"
            path.write_text(script, encoding="utf-8")
            proc = subprocess.run(
                ["python", str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=td,
            )
            ok = proc.returncode == 0 and "OK" in proc.stdout
            return {
                "correct": ok,
                "predicted": code[:500],
                "expected": "tests_pass",
                "grader": "code_tests",
                "stdout": proc.stdout[-500:],
                "stderr": proc.stderr[-500:],
            }
    except subprocess.TimeoutExpired:
        return {"correct": False, "predicted": code[:500], "expected": "tests_pass", "grader": "code_tests", "error": "timeout"}
    except Exception as e:
        return {"correct": False, "predicted": code[:500], "expected": "tests_pass", "grader": "code_tests", "error": str(e)}


def grade_tool_answer(predicted: str, expected: str, params: dict[str, Any]) -> dict[str, Any]:
    domain = params.get("domain", "math")
    tol = float(params.get("tolerance", 1e-3))
    pred = normalize_answer(predicted, domain)
    exp = normalize_answer(expected, domain)
    ok = answers_equal(pred, exp, domain, tol)
    return {"correct": ok, "predicted": pred, "expected": exp, "grader": "tool_answer"}
