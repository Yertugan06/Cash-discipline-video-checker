"""Unit tests for `backend.rules.rank`: persistence first, then rules.yaml order, then cap."""

from __future__ import annotations

from backend.contracts import Finding, RuleEntry
from backend.rules import rank


def _rule(rule_id: str) -> RuleEntry:
    return RuleEntry(
        rule_id=rule_id,
        title_ru=rule_id,
        title_en=rule_id,
        mechanism="m",
        states_used=[],
        params={},
        description_template="t={t}",
        visibility_caveat="v",
        norm_ids=["n1"],
        enabled=True,
    )


def _finding(rule_id: str, rank_score: float, t: float = 0.0) -> Finding:
    return Finding(
        rule_id=rule_id,
        t_anchor=t,
        t_start=t,
        t_end=t,
        support_t=[t],
        facts={},
        rank_score=rank_score,
    )


def test_persistence_breaks_ties_first():
    rules = [_rule("A"), _rule("B")]
    findings = [_finding("A", rank_score=1.0), _finding("B", rank_score=5.0)]
    ranked = rank(findings, rules, cap=3)
    assert [f.rule_id for f in ranked] == ["B", "A"]


def test_rule_order_breaks_ties_on_equal_persistence():
    rules = [_rule("A"), _rule("B"), _rule("C")]
    findings = [_finding(r, rank_score=2.0) for r in ("C", "A", "B")]
    ranked = rank(findings, rules, cap=3)
    assert [f.rule_id for f in ranked] == ["A", "B", "C"]


def test_cap_limits_output():
    rules = [_rule("A"), _rule("B"), _rule("C"), _rule("D")]
    findings = [_finding(r, rank_score=float(i)) for i, r in enumerate(["D", "C", "B", "A"])]
    ranked = rank(findings, rules, cap=2)
    assert len(ranked) == 2
    assert [f.rule_id for f in ranked] == ["A", "B"]


def test_unknown_rule_id_falls_back_to_the_end():
    rules = [_rule("A")]
    findings = [_finding("A", rank_score=1.0), _finding("ZZZ-UNKNOWN", rank_score=1.0)]
    ranked = rank(findings, rules, cap=5)
    assert [f.rule_id for f in ranked] == ["A", "ZZZ-UNKNOWN"]


def test_empty_findings_returns_empty():
    assert rank([], [_rule("A")], cap=3) == []


def test_confirmed_exit_is_only_a_tie_break_after_score_and_rule_order():
    rules = [_rule("A"), _rule("B")]
    confirmed = _finding("B", rank_score=1.0)
    confirmed.facts["confirmed_exit"] = True
    earlier_rule = _finding("A", rank_score=1.0)
    stronger = _finding("B", rank_score=2.0)
    assert rank([confirmed, earlier_rule, stronger], rules) == [stronger, earlier_rule, confirmed]
