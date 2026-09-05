"""Core shared types for SampleMoreStudio."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Phase = Literal["phase1_reasoning", "phase2_agent"]


@dataclass
class Turn:
    role: str  # system | user | assistant | tool_call | tool_result
    content: str
    tokens: int
    label: str | None = None
    timestamp: float = 0.0
    truncated: bool = False
    prompt_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Turn:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class StrategyResult:
    final_answer: str
    tokens_spent: int
    transcript: list[Turn]
    metadata: dict[str, Any] = field(default_factory=dict)
    prompt_tokens_spent: int = 0
    budget_exhausted: bool = False
    overshoot_flagged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "tokens_spent": self.tokens_spent,
            "prompt_tokens_spent": self.prompt_tokens_spent,
            "transcript": [t.to_dict() for t in self.transcript],
            "metadata": self.metadata,
            "budget_exhausted": self.budget_exhausted,
            "overshoot_flagged": self.overshoot_flagged,
        }


@dataclass
class Task:
    id: str
    phase: Phase
    category: str
    prompt: str
    answer: str
    grader: str
    grader_params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    content: str
    completion_tokens: int
    prompt_tokens: int
    truncated: bool
    finish_reason: str | None = None
    raw: Any = None


@dataclass
class ModelConfig:
    id: str
    litellm_model: str
    provider: str
    local: bool
    cost_per_1k_completion: float
    cost_per_1k_prompt: float
    enabled: bool = True
    notes: str = ""
