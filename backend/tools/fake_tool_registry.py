"""Sandboxed fake tools for Phase 2 agent tasks — deterministic, no real I/O."""
from __future__ import annotations

import json
import operator
import re
from typing import Any, Callable


class FakeFilesystem:
    def __init__(self, files: dict[str, str]):
        self.files = dict(files)

    def read_file(self, path: str) -> str:
        if path not in self.files:
            return f"ERROR: file not found: {path}"
        return self.files[path]

    def list_dir(self, path: str = "/") -> str:
        prefix = path.rstrip("/") + "/" if path not in ("", "/") else ""
        names = sorted({p[len(prefix):].split("/")[0] for p in self.files if p.startswith(prefix) or path in ("", "/")})
        if path in ("", "/"):
            names = sorted({p.split("/")[0] for p in self.files})
        return "\n".join(names) if names else "(empty)"

    def search(self, query: str) -> str:
        hits = []
        for path, content in self.files.items():
            if query.lower() in content.lower() or query.lower() in path.lower():
                hits.append(f"{path}: {content[:120]}")
        return "\n".join(hits) if hits else "No matches"


class FakeJSONStore:
    def __init__(self, data: Any):
        self.data = data

    def get(self, path: str) -> str:
        """Dot-path get, e.g. users.0.name"""
        cur: Any = self.data
        if not path or path == ".":
            return json.dumps(cur)
        for part in path.split("."):
            if isinstance(cur, list):
                try:
                    cur = cur[int(part)]
                except (ValueError, IndexError):
                    return f"ERROR: invalid path {path}"
            elif isinstance(cur, dict):
                if part not in cur:
                    return f"ERROR: key not found: {part}"
                cur = cur[part]
            else:
                return f"ERROR: cannot traverse {path}"
        return json.dumps(cur)

    def keys(self, path: str = "") -> str:
        cur: Any = self.data
        if path:
            raw = self.get(path)
            try:
                cur = json.loads(raw)
            except json.JSONDecodeError:
                return raw
        if isinstance(cur, dict):
            return json.dumps(list(cur.keys()))
        if isinstance(cur, list):
            return json.dumps(list(range(len(cur))))
        return json.dumps([])


class FakeCalculator:
    OPS = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        "**": operator.pow,
    }

    def calc(self, expression: str) -> str:
        expr = expression.strip()
        # Very small safe evaluator: numbers and + - * / ** and parentheses via ast-like regex split
        try:
            # Allow only safe characters
            if not re.fullmatch(r"[0-9+\-*/().\s**]+", expr.replace("**", "")):
                # retry with **
                if not re.fullmatch(r"[0-9+\-*/().\s*]+", expr):
                    return "ERROR: invalid expression"
            result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 — constrained charset
            return str(result)
        except Exception as e:
            return f"ERROR: {e}"


ToolFn = Callable[..., str]


class FakeToolRegistry:
    """Registry of tools available for a given task."""

    def __init__(self, tools: dict[str, ToolFn], descriptions: dict[str, str] | None = None):
        self.tools = tools
        self.descriptions = descriptions or {k: k for k in tools}

    def list_tools(self) -> str:
        lines = [f"- {name}: {self.descriptions.get(name, '')}" for name in self.tools]
        return "\n".join(lines)

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self.tools:
            return f"ERROR: unknown tool {name}"
        try:
            return str(self.tools[name](**arguments))
        except TypeError as e:
            return f"ERROR: bad arguments: {e}"
        except Exception as e:
            return f"ERROR: {e}"


def build_registry_for_task(task_meta: dict[str, Any]) -> FakeToolRegistry:
    kind = task_meta.get("tool_kind", "file")
    if kind == "file":
        fs = FakeFilesystem(task_meta.get("files", {}))
        return FakeToolRegistry(
            {
                "read_file": fs.read_file,
                "list_dir": fs.list_dir,
                "search": fs.search,
            },
            {
                "read_file": "read_file(path: str) -> file contents",
                "list_dir": "list_dir(path: str = '/') -> directory listing",
                "search": "search(query: str) -> matching lines",
            },
        )
    if kind == "json":
        store = FakeJSONStore(task_meta.get("data", {}))
        return FakeToolRegistry(
            {
                "json_get": store.get,
                "json_keys": store.keys,
            },
            {
                "json_get": "json_get(path: str) -> JSON value at dot-path",
                "json_keys": "json_keys(path: str = '') -> keys/indices",
            },
        )
    if kind == "calc":
        calc = FakeCalculator()
        return FakeToolRegistry(
            {"calculator": calc.calc},
            {"calculator": "calculator(expression: str) -> numeric result"},
        )
    raise ValueError(f"Unknown tool_kind: {kind}")


TOOL_CALL_RE = re.compile(
    r"Action\s*:\s*(\w+)\s*\n\s*Action Input\s*:\s*(\{.*?\})",
    re.IGNORECASE | re.DOTALL,
)
FINAL_RE = re.compile(r"Final Answer\s*:\s*(.+)", re.IGNORECASE)


def parse_agent_action(text: str) -> tuple[str, dict[str, Any] | None, str | None]:
    """Return (kind, tool_args_or_none, final_answer_or_none).

    kind in {'tool', 'final', 'none'}
    """
    final = FINAL_RE.search(text)
    # Prefer Final Answer if present at end
    action = TOOL_CALL_RE.search(text)
    if action and (not final or action.start() < final.start()):
        name = action.group(1)
        try:
            args = json.loads(action.group(2))
        except json.JSONDecodeError:
            args = {}
        return "tool", {"name": name, "arguments": args}, None
    if final:
        return "final", None, final.group(1).strip()
    # Also accept Answer: tag
    from backend.answer_extraction import extract_answer

    ans = extract_answer(text, "math")
    if ans and "Action:" not in text:
        return "final", None, ans
    return "none", None, None
