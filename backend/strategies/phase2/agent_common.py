"""Shared Phase-2 agent loop helpers."""
from __future__ import annotations

from backend.adapters.litellm_adapter import ModelAdapter
from backend.answer_extraction import extract_answer
from backend.strategies.base import Strategy
from backend.token_budget import BudgetTracker
from backend.tools.fake_tool_registry import (
    FakeToolRegistry,
    build_registry_for_task,
    parse_agent_action,
)
from backend.types import StrategyResult, Task, Turn


AGENT_FORMAT = """You have access to tools. Use this exact format:

Thought: reason about what to do
Action: tool_name
Action Input: {"arg": "value"}

When you know the answer, output:
Thought: ...
Final Answer: <answer>

Also end with: Answer: <answer>
"""


class AgentLoopMixin(Strategy):
    phase = "phase2_agent"

    def _registry(self, task: Task) -> FakeToolRegistry:
        return build_registry_for_task(task.metadata)

    def _agent_system(self, task: Task, registry: FakeToolRegistry) -> str:
        return (
            "You are a tool-using agent.\n"
            + AGENT_FORMAT
            + "\nAvailable tools:\n"
            + registry.list_tools()
        )

    def run_agent_loop(
        self,
        task: Task,
        model: ModelAdapter,
        tracker: BudgetTracker,
        extra_system: str = "",
        max_turns: int | None = None,
        label_prefix: str = "",
    ) -> tuple[str, list[Turn], dict]:
        registry = self._registry(task)
        system = self._agent_system(task, registry) + (("\n" + extra_system) if extra_system else "")
        transcript: list[Turn] = [
            self._make_turn("system", system, 0, label=f"{label_prefix}system"),
            self._make_turn("user", task.prompt, 0, label=f"{label_prefix}user"),
        ]
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": task.prompt},
        ]
        tool_calls = 0
        final_answer = ""
        turns = max_turns or len(tracker.plan.allocations)

        for i in range(turns):
            cap = tracker.next_cap()
            if cap <= 0:
                # Best answer so far fallback
                if not final_answer:
                    final_answer = extract_answer(
                        next((t.content for t in reversed(transcript) if t.role == "assistant"), ""),
                        task.grader_params.get("domain", "math"),
                    )
                break
            gen = model.generate(messages, max_tokens=cap)
            tracker.record(gen.completion_tokens, gen.prompt_tokens)
            transcript.append(
                self._make_turn(
                    "assistant",
                    gen.content,
                    gen.completion_tokens,
                    label=f"{label_prefix}agent_turn_{i + 1}",
                    truncated=gen.truncated,
                    prompt_tokens=gen.prompt_tokens,
                )
            )
            messages.append({"role": "assistant", "content": gen.content})

            kind, tool_info, final = parse_agent_action(gen.content)
            if kind == "final" and final:
                final_answer = final
                break
            if kind == "tool" and tool_info:
                name = tool_info["name"]
                args = tool_info["arguments"]
                result = registry.call(name, args)
                tool_calls += 1
                observation = f"Observation: {result}"
                transcript.append(
                    self._make_turn(
                        "tool_call",
                        json_dumps({"name": name, "arguments": args}),
                        0,
                        label=f"{label_prefix}tool_call:{name}",
                    )
                )
                transcript.append(
                    self._make_turn(
                        "tool_result",
                        observation,
                        0,
                        label=f"{label_prefix}tool_result:{name}",
                    )
                )
                messages.append({"role": "user", "content": observation})
            else:
                # No parseable action — nudge once then continue
                messages.append(
                    {
                        "role": "user",
                        "content": "Continue. Use Action/Action Input or provide Final Answer.",
                    }
                )

        if not final_answer:
            final_answer = extract_answer(
                next((t.content for t in reversed(transcript) if t.role == "assistant"), ""),
                task.grader_params.get("domain", "math"),
            )

        return final_answer, transcript, {"tool_calls": tool_calls}


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj)
