"""Unit tests for `backend.rules.evaluate`, independent of the kit (no private data needed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.knowledge import Knowledge
from backend.rules import evaluate
from tests.fixtures.rules.builder import AWAY, GONE, make_timeline

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"


@pytest.fixture(scope="module")
def rules():
    return Knowledge.load(KNOWLEDGE_ROOT).rules


def _ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


# ---------------------------------------------------------------------------------------------
# Cash left on the desk while the cashier is away, vs. its clean counterpart (cash put away).
# ---------------------------------------------------------------------------------------------


def test_cash_left_on_desk_fires(rules):
    tl = make_timeline(
        "cash-left",
        20,
        [(0, 20, {"desk_cash": True}), (8, 12, AWAY), (12, 20, GONE)],
    )
    findings = evaluate(tl, rules)
    assert "L-NO-CASH-ON-LEAVE" in _ids(findings)
    f = next(x for x in findings if x.rule_id == "L-NO-CASH-ON-LEAVE")
    assert f.t_anchor == 8.0
    assert f.facts["object"] in ("наличные", "сумка", "наличные и сумка")
    assert f.t_start == 8.0 and f.t_end == 20.0
    assert f.support_t  # persistence evidence present


def test_cash_cleared_before_leaving_is_clean(rules):
    tl = make_timeline(
        "cash-cleared",
        20,
        [(8, 12, AWAY), (12, 20, GONE)],  # desk_cash never set True anywhere
    )
    findings = evaluate(tl, rules)
    assert "L-NO-CASH-ON-LEAVE" not in _ids(findings)


# ---------------------------------------------------------------------------------------------
# Unlocked laptop while the cashier is away, vs. its clean counterpart (screen locked first).
# ---------------------------------------------------------------------------------------------


def test_unlocked_laptop_while_away_fires(rules):
    tl = make_timeline(
        "laptop-unlocked",
        16,
        [(0, 16, {"laptop_screen": "unlocked"}), (7, 11, AWAY), (11, 16, GONE)],
    )
    findings = evaluate(tl, rules)
    assert "L-PC-LOCKED" in _ids(findings)
    f = next(x for x in findings if x.rule_id == "L-PC-LOCKED")
    assert f.t_anchor == 7.0


def test_laptop_locked_before_leaving_is_clean(rules):
    tl = make_timeline(
        "laptop-locked",
        17,
        [(6, 17, {"laptop_screen": "lock_screen"}), (7, 11, AWAY), (11, 17, GONE)],
    )
    findings = evaluate(tl, rules)
    assert "L-PC-LOCKED" not in _ids(findings)


# ---------------------------------------------------------------------------------------------
# Persistence / min_samples: an absence shorter than min_away_s must not fire.
# ---------------------------------------------------------------------------------------------


def test_away_shorter_than_threshold_does_not_fire(rules):
    # min_away_s=3.0 at 1 s sampling -> need >= 3 consecutive away samples. Only 1 here.
    tl = make_timeline(
        "brief-away",
        10,
        [(0, 10, {"desk_cash": True}), (5, 6, AWAY)],
    )
    findings = evaluate(tl, rules)
    assert "L-NO-CASH-ON-LEAVE" not in _ids(findings)


def test_away_at_threshold_fires(rules):
    tl = make_timeline(
        "exact-away",
        10,
        [(0, 10, {"desk_cash": True}), (5, 8, AWAY)],  # 3 consecutive samples: 5, 6, 7
    )
    findings = evaluate(tl, rules)
    assert "L-NO-CASH-ON-LEAVE" in _ids(findings)


# ---------------------------------------------------------------------------------------------
# ok=False frames are unknown, never negative evidence.
# ---------------------------------------------------------------------------------------------


def test_unknown_frames_are_dropped_not_negative(rules):
    """A couple of failed samples inside the away run must not break detection -- they are
    simply absent from the (now-sparser) timeline, not treated as 'cashier at desk'."""
    tl_clean = make_timeline(
        "away-with-gaps",
        20,
        [(0, 20, {"desk_cash": True}), (8, 12, AWAY), (12, 20, GONE)],
    )
    tl_gappy = make_timeline(
        "away-with-gaps",
        20,
        [(0, 20, {"desk_cash": True}), (8, 12, AWAY), (12, 20, GONE)],
        unknown_t={9, 10},
    )
    findings_clean = evaluate(tl_clean, rules)
    findings_gappy = evaluate(tl_gappy, rules)
    assert "L-NO-CASH-ON-LEAVE" in _ids(findings_clean)
    assert "L-NO-CASH-ON-LEAVE" in _ids(findings_gappy)


def test_all_frames_unknown_yields_no_findings(rules):
    tl = make_timeline(
        "all-unknown",
        10,
        [(0, 10, {"desk_cash": True}), (5, 8, AWAY)],
        unknown_t=set(range(0, 11)),
    )
    assert evaluate(tl, rules) == []


def test_disabled_rule_never_fires(rules):
    """C-DETECTOR-CHECK is disabled in the production Knowledge Pack; even a timeline that would
    satisfy its condition must not produce a finding for it."""
    tl = make_timeline(
        "hand-count-no-detector",
        10,
        [(0, 10, {"cashier_action": "counting_by_hand"})],
    )
    findings = evaluate(tl, rules)
    assert "C-DETECTOR-CHECK" not in _ids(findings)


def test_empty_timeline_yields_no_findings(rules):
    tl = make_timeline("empty", 5, [], unknown_t=set(range(0, 6)))
    assert evaluate(tl, rules) == []
