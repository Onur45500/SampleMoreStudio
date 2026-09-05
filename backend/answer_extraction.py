"""Answer extraction and normalization for grading and majority vote."""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Any


ANSWER_TAG_RE = re.compile(
    r"(?:^|\n)\s*(?:final\s+)?answer\s*[:：]\s*(.+?)(?:\n|$)",
    re.IGNORECASE | re.DOTALL,
)
BOXED_RE = re.compile(r"\\boxed\{([^}]+)\}")
LAST_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?")


def extract_answer(text: str, domain: str = "math") -> str:
    """Extract the final answer from model output using forced format first."""
    if not text:
        return ""

    # Prefer explicit Answer: tag
    matches = list(ANSWER_TAG_RE.finditer(text))
    if matches:
        raw = matches[-1].group(1).strip()
        raw = raw.strip("`\"' ")
        # Stop at first semicolon/period if long prose leaked in
        if domain != "code" and len(raw) > 80:
            raw = re.split(r"[;\n]", raw)[0].strip()
        return normalize_answer(raw, domain)

    boxed = BOXED_RE.findall(text)
    if boxed:
        return normalize_answer(boxed[-1].strip(), domain)

    if domain == "code":
        # Return whole text for code; grader runs tests
        return text.strip()

    # Fallback: last number-like token
    nums = LAST_NUMBER_RE.findall(text.replace(",", ""))
    if nums:
        return normalize_answer(nums[-1], domain)

    # Last non-empty line
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return normalize_answer(lines[-1] if lines else "", domain)


def normalize_answer(raw: str, domain: str = "math") -> str:
    s = raw.strip()
    s = s.strip("`\"' ")
    s = re.sub(r"\s+", " ", s)

    if domain in ("math", "calc"):
        return _normalize_numeric(s)
    if domain == "logic":
        return s.lower().rstrip(".")
    if domain == "code":
        return s
    return s


def _normalize_numeric(s: str) -> str:
    s = s.replace(",", "").replace("$", "").replace("%", "").strip()
    # Fraction a/b
    if re.fullmatch(r"[-+]?\d+\s*/\s*\d+", s):
        try:
            return str(float(Fraction(s.replace(" ", ""))))
        except (ValueError, ZeroDivisionError):
            return s
    # Plain number
    try:
        f = float(s)
        if f == int(f) and abs(f) < 1e15:
            return str(int(f))
        # Canonical float string without trailing zeros noise for vote keys
        return f"{f:.10g}"
    except ValueError:
        return s.lower()


def answers_equal(a: str, b: str, domain: str = "math", tolerance: float = 1e-3) -> bool:
    na = normalize_answer(a, domain)
    nb = normalize_answer(b, domain)
    if domain in ("math", "calc"):
        try:
            return abs(float(na) - float(nb)) <= tolerance
        except ValueError:
            return na == nb
    return na == nb


def majority_vote(answers: list[str], domain: str = "math") -> tuple[str, dict[str, Any]]:
    """Return winning answer and vote breakdown (normalized keys)."""
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for ans in answers:
        key = normalize_answer(ans, domain)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        originals.setdefault(key, ans)
    if not counts:
        return "", {"votes": {}, "winner": None, "tie": False}
    # Sort by count desc, then by first-seen order via originals insertion
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], list(originals.keys()).index(kv[0])))
    winner_key = ranked[0][0]
    tie = len(ranked) > 1 and ranked[0][1] == ranked[1][1]
    return originals[winner_key], {
        "votes": counts,
        "winner": winner_key,
        "tie": tie,
        "n_valid": sum(counts.values()),
    }


ANSWER_INSTRUCTION = (
    "Think step by step. End your response with a single line of the form:\n"
    "Answer: <your final answer>"
)
