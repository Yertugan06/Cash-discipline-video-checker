"""`eval.coverage` gap categories, on synthetic annotations against the real rulebook."""

from __future__ import annotations

import copy

import yaml

from eval.coverage import _code_match, coverage
from scripts.build_knowledge import RULEBOOK, Rulebook

CODE_MATCH = _code_match()


def _rb(mutate=None) -> Rulebook:
    data = yaml.safe_load(RULEBOOK.read_text(encoding="utf-8"))
    if mutate:
        data = copy.deepcopy(data)
        mutate(data)
    return Rulebook.model_validate(data)


def _video(*clauses, reliable=True, violation=True):
    return {"violation": violation, "human_reliable": reliable,
            "human": [{"norm1": c} for c in clauses]}  # fmt: skip


def _cat(video, rb=None):
    return coverage({"X-1": video}, rb or _rb(), CODE_MATCH)["X-1"]["category"]


def test_categories():
    assert _cat(_video("п. 12 ч. 1")) == "covered_pending"  # W-NO-PERSONAL-ITEMS, enabled
    assert _cat(_video("п. 59")) == "rule_without_norm"  # only C-REJECT-NOT-RETURNED's hint
    assert _cat(_video("п. 99 ч. 9")) == "clause_not_in_rulebook"
    assert _cat(_video("п. 99 ч. 9", reliable=False)) == "annotation_unreliable"
    assert _cat(_video()) == "no_annotation"
    assert coverage({"X-2": _video(violation=False)}, _rb(), CODE_MATCH) == {}


def test_best_clause_wins_and_verification_counts():
    def verify(d):
        d["norms"]["231-12-1"].update(
            citation_status="verified", verified_by="r", verified_at="2026-10-18"
        )

    assert _cat(_video("п. 99", "п. 12 ч. 1"), _rb(verify)) == "covered_verified"


def test_disabled_rules_say_why():
    def disable(d):
        rule = d["rules"]["W-NO-PERSONAL-ITEMS"]
        rule.update(enabled=False, disabled_reason="not observable from above")

    assert _cat(_video("п. 12 ч. 1"), _rb(disable)) == "rule_disabled_other"
    # п. 19 пп. 2) is cited only by C-DETECTOR-CHECK, which has no evaluator
    assert _cat(_video("п. 19 пп. 2)")) == "rule_without_evaluator"
