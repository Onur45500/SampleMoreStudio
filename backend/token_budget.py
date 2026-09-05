"""Token budget engine — credibility-critical equal-cost allocator.

Budget metric: completion tokens only (primary). Prompt tokens are recorded
alongside but do not consume the budget. Invariant: never exceed B; undershoot
is normal. Overshoot > tolerance_pct is flagged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SplitPolicy = Literal["even", "front_loaded"]


def scaled_sample_cap(
    budget: int,
    fraction: float = 0.25,
    floor: int = 128,
    absolute: int | None = None,
) -> int:
    """Per-sample completion cap scaled with B: max(floor, B * fraction).

    If `absolute` is set (legacy fixed mode), use that instead of scaling.
    """
    if absolute is not None and absolute > 0:
        return int(absolute)
    return max(int(floor), int(budget * fraction))


def scaled_selection_cap(
    budget: int,
    fraction: float = 0.125,
    floor: int = 64,
    absolute: int | None = None,
) -> int:
    if absolute is not None and absolute > 0:
        return int(absolute)
    return max(int(floor), int(budget * fraction))


def resolve_caps_from_config(budget: int, budgets_cfg: dict | None = None) -> tuple[int, int]:
    """Return (sample_cap, selection_cap) for budget B using config fractions."""
    cfg = budgets_cfg or {}
    # Legacy fixed overrides win only when scale_with_budget is false
    scale = bool(cfg.get("scale_with_budget", True))
    sample_frac = float(cfg.get("sample_fraction", 0.25))
    sel_frac = float(cfg.get("selection_fraction", 0.125))
    sample_floor = int(cfg.get("sample_token_floor", cfg.get("sample_token_cap", 128)))
    sel_floor = int(cfg.get("selection_token_floor", cfg.get("selection_token_cap", 64)))
    if not scale:
        return (
            int(cfg.get("sample_token_cap", sample_floor)),
            int(cfg.get("selection_token_cap", sel_floor)),
        )
    return (
        scaled_sample_cap(budget, sample_frac, sample_floor),
        scaled_selection_cap(budget, sel_frac, sel_floor),
    )


@dataclass
class BudgetPlan:
    """Allocation plan for a strategy given total completion budget B."""

    total_budget: int
    allocations: list[int]  # per-call max_tokens caps
    labels: list[str]
    n_samples: int | None = None
    metadata: dict | None = None

    def remaining_after(self, spent: int) -> int:
        return max(0, self.total_budget - spent)


def cot_plan(budget: int) -> BudgetPlan:
    return BudgetPlan(
        total_budget=budget,
        allocations=[budget],
        labels=["cot"],
        n_samples=1,
        metadata={"formula": "max_tokens = B"},
    )


def self_refine_plan(
    budget: int,
    rounds: int = 3,
    split: SplitPolicy = "even",
) -> BudgetPlan:
    """Even split: initial + R*(critique + revision) = 2R+1 slices.

    Unspent tokens roll forward at call time (handled by BudgetTracker).
    """
    n_slices = 2 * rounds + 1
    if split == "even":
        base = budget // n_slices
        rem = budget % n_slices
        allocations = [base + (1 if i < rem else 0) for i in range(n_slices)]
    else:
        # Front-loaded: give ~40% to initial, rest even across refine steps
        initial = max(1, int(budget * 0.4))
        rest = budget - initial
        per = rest // (n_slices - 1) if n_slices > 1 else 0
        rem = rest % (n_slices - 1) if n_slices > 1 else 0
        allocations = [initial]
        for i in range(n_slices - 1):
            allocations.append(per + (1 if i < rem else 0))

    labels = ["initial"]
    for r in range(1, rounds + 1):
        labels.append(f"critique_round_{r}")
        labels.append(f"revision_round_{r}")

    return BudgetPlan(
        total_budget=budget,
        allocations=allocations,
        labels=labels,
        n_samples=1,
        metadata={
            "formula": f"even_split B/(2R+1) with R={rounds}",
            "rounds": rounds,
            "split": split,
        },
    )


def best_of_n_plan(
    budget: int,
    sample_cap: int = 128,
    selection_cap: int = 64,
) -> BudgetPlan:
    """N = floor((B - S_sel) / S_sample); leftover goes to last sample."""
    if budget <= selection_cap + sample_cap:
        # Degenerate: single sample, no selection
        return BudgetPlan(
            total_budget=budget,
            allocations=[budget],
            labels=["sample_1_of_1"],
            n_samples=1,
            metadata={
                "formula": "N=1 (budget too small for selection)",
                "n": 1,
                "sample_cap": sample_cap,
                "selection_cap": selection_cap,
            },
        )

    n = max(1, (budget - selection_cap) // sample_cap)
    sample_budget = budget - selection_cap
    per = sample_budget // n
    rem = sample_budget % n
    allocations = [per + (1 if i < rem else 0) for i in range(n)]
    allocations.append(selection_cap)
    labels = [f"sample_{i + 1}_of_{n}" for i in range(n)] + ["self_selection"]
    return BudgetPlan(
        total_budget=budget,
        allocations=allocations,
        labels=labels,
        n_samples=n,
        metadata={
            "formula": f"N=floor((B-{selection_cap})/{sample_cap})",
            "n": n,
            "n_or_k": n,
            "sample_cap": sample_cap,
            "per_sample_cap": sample_cap,
            "selection_cap": selection_cap,
        },
    )


def majority_vote_plan(
    budget: int,
    sample_cap: int = 128,
) -> BudgetPlan:
    """K = floor(B / S_sample); selection is free (counting)."""
    k = max(1, budget // sample_cap)
    per = budget // k
    rem = budget % k
    allocations = [per + (1 if i < rem else 0) for i in range(k)]
    labels = [f"sample_{i + 1}_of_{k}" for i in range(k)]
    return BudgetPlan(
        total_budget=budget,
        allocations=allocations,
        labels=labels,
        n_samples=k,
        metadata={
            "formula": f"K=floor(B/{sample_cap})",
            "k": k,
            "n_or_k": k,
            "sample_cap": sample_cap,
            "per_sample_cap": sample_cap,
            "selection": "free_majority_vote",
        },
    )


def agent_loop_plan(budget: int, max_turns: int = 12) -> BudgetPlan:
    """Phase 2: equal slices across up to max_turns reasoning steps.

    Strategies may early-stop; BudgetTracker enforces remaining budget.
    """
    per = max(1, budget // max_turns)
    allocations = [per] * max_turns
    # Give remainder to first turn
    allocations[0] += budget - per * max_turns
    labels = [f"agent_turn_{i + 1}" for i in range(max_turns)]
    return BudgetPlan(
        total_budget=budget,
        allocations=allocations,
        labels=labels,
        n_samples=None,
        metadata={"formula": f"loop_cap={max_turns}, per≈B/{max_turns}", "max_turns": max_turns},
    )


def majority_of_n_agent_plan(
    budget: int,
    n: int | None = None,
    sample_cap: int | None = None,
) -> BudgetPlan:
    """Split B across N independent full agent attempts."""
    if n is None:
        cap = sample_cap or max(64, budget // 3)
        n = max(1, budget // cap)
    per = budget // n
    rem = budget % n
    allocations = [per + (1 if i < rem else 0) for i in range(n)]
    labels = [f"agent_attempt_{i + 1}_of_{n}" for i in range(n)]
    return BudgetPlan(
        total_budget=budget,
        allocations=allocations,
        labels=labels,
        n_samples=n,
        metadata={"formula": f"N independent attempts, N={n}", "n": n},
    )


class BudgetTracker:
    """Tracks completion-token spend against a plan; never allows exceeding B."""

    def __init__(self, plan: BudgetPlan, overshoot_tolerance_pct: float = 10.0):
        self.plan = plan
        self.overshoot_tolerance_pct = overshoot_tolerance_pct
        self.spent = 0
        self.prompt_spent = 0
        self.call_index = 0
        self.budget_exhausted = False

    @property
    def remaining(self) -> int:
        return max(0, self.plan.total_budget - self.spent)

    def next_cap(self, preferred: int | None = None) -> int:
        """Return max_tokens for the next call, capped by remaining budget."""
        if self.remaining <= 0:
            self.budget_exhausted = True
            return 0
        if preferred is not None:
            return min(preferred, self.remaining)
        if self.call_index < len(self.plan.allocations):
            alloc = self.plan.allocations[self.call_index]
            # Roll forward: give unused prior allocation + this slice, still ≤ remaining
            return min(max(alloc, 1), self.remaining)
        return self.remaining

    def record(self, completion_tokens: int, prompt_tokens: int = 0) -> None:
        self.spent += completion_tokens
        self.prompt_spent += prompt_tokens
        self.call_index += 1
        if self.spent >= self.plan.total_budget:
            self.budget_exhausted = True

    def overshoot_flagged(self) -> bool:
        if self.plan.total_budget <= 0:
            return False
        overshoot_pct = ((self.spent - self.plan.total_budget) / self.plan.total_budget) * 100
        return overshoot_pct > self.overshoot_tolerance_pct

    def status(self) -> dict:
        return {
            "target": self.plan.total_budget,
            "spent": self.spent,
            "prompt_spent": self.prompt_spent,
            "remaining": self.remaining,
            "overshoot_flagged": self.overshoot_flagged(),
            "budget_exhausted": self.budget_exhausted,
            "undershoot": max(0, self.plan.total_budget - self.spent),
        }
