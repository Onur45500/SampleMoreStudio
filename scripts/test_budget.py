"""Unit tests for budget-splitting formulas."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.token_budget import (
    BudgetTracker,
    best_of_n_plan,
    cot_plan,
    majority_vote_plan,
    resolve_caps_from_config,
    scaled_sample_cap,
    scaled_selection_cap,
    self_refine_plan,
)


def test_cot_uses_full_budget():
    p = cot_plan(512)
    assert p.allocations == [512]


def test_self_refine_even_split():
    p = self_refine_plan(700, rounds=3, split="even")
    assert len(p.allocations) == 7  # 2*3+1
    assert sum(p.allocations) == 700


def test_best_of_n_formula():
    p = best_of_n_plan(512, sample_cap=128, selection_cap=64)
    assert p.n_samples == 3
    assert len(p.allocations) == 4
    assert sum(p.allocations) == 512


def test_majority_vote_larger_than_bon():
    bon = best_of_n_plan(512, 128, 64)
    mv = majority_vote_plan(512, 128)
    assert mv.n_samples is not None and bon.n_samples is not None
    assert mv.n_samples >= bon.n_samples
    assert sum(mv.allocations) == 512


def test_tracker_never_exceeds_via_cap():
    p = cot_plan(100)
    t = BudgetTracker(p)
    assert t.next_cap() == 100
    t.record(80)
    assert t.next_cap() == 20
    t.record(20)
    assert t.next_cap() == 0
    assert t.budget_exhausted


def test_overshoot_flag():
    p = cot_plan(100)
    t = BudgetTracker(p, overshoot_tolerance_pct=10)
    t.record(105)
    assert not t.overshoot_flagged()
    t2 = BudgetTracker(p, overshoot_tolerance_pct=10)
    t2.record(120)
    assert t2.overshoot_flagged()


def test_answer_extraction():
    from backend.answer_extraction import extract_answer, majority_vote

    assert extract_answer("stuff\nAnswer: 42\n") == "42"
    assert extract_answer("Answer: 1/2") in ("0.5", "1/2")
    w, b = majority_vote(["42", "42", "7"], "math")
    assert w == "42"
    assert b["votes"]["42"] == 2


def test_scaled_caps_grow_with_budget():
    caps = []
    for b in (256, 512, 1024, 2048):
        sc = scaled_sample_cap(b, fraction=0.25, floor=128)
        sel = scaled_selection_cap(b, fraction=0.125, floor=64)
        caps.append((b, sc, sel))
        assert sc >= 128
        assert sel >= 64
        assert cot_plan(b).allocations == [b]
        mv = majority_vote_plan(b, sc)
        bon = best_of_n_plan(b, sc, sel)
        assert (mv.n_samples or 0) >= 1
        assert (bon.n_samples or 0) >= 1
        assert sum(mv.allocations) == b
        assert sum(bon.allocations) == b
    assert caps[0][1] <= caps[1][1] <= caps[2][1] <= caps[3][1]
    assert scaled_sample_cap(1024) == 256
    assert scaled_sample_cap(256) == 128


def test_resolve_caps_from_config_scaled():
    cfg = {
        "scale_with_budget": True,
        "sample_fraction": 0.25,
        "selection_fraction": 0.125,
        "sample_token_floor": 128,
        "selection_token_floor": 64,
    }
    sc, sel = resolve_caps_from_config(2048, cfg)
    assert sc == 512
    assert sel == 256


if __name__ == "__main__":
    test_cot_uses_full_budget()
    test_self_refine_even_split()
    test_best_of_n_formula()
    test_majority_vote_larger_than_bon()
    test_tracker_never_exceeds_via_cap()
    test_overshoot_flag()
    test_answer_extraction()
    test_scaled_caps_grow_with_budget()
    test_resolve_caps_from_config_scaled()
    print("All budget/extraction tests passed.")
