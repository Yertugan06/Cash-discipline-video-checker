"""`scripts/import_norm_review.apply_reviews`: only unambiguous verdicts are applied."""

from __future__ import annotations

import copy

import pytest
import yaml

from scripts.build_knowledge import RULEBOOK, Rulebook, jury_blockers
from scripts.import_norm_review import _header, apply_reviews

DATA = yaml.safe_load(RULEBOOK.read_text(encoding="utf-8"))
NAMES = {"u_1": "Reviewer One"}


def _review(norm_id, **kw):
    base = {"norm_id": norm_id, "quote": "matches", "in_force": "yes", "rules": {},
            "corrected_punkt": "", "note": "", "reviewer": "u_1",
            "updated_at": "2026-10-18T09:00:00Z"}  # fmt: skip
    return {**base, **kw}


def test_verified_norm_and_act_make_a_rule_jury_eligible():
    data, applied, manual = apply_reviews(
        copy.deepcopy(DATA),
        [_review("231-12-1", rules={"W-NO-PERSONAL-ITEMS": "direct"})],
        NAMES,
    )
    norm = data["norms"]["231-12-1"]
    assert (norm["citation_status"], norm["verified_by"], norm["verified_at"]) == (
        "verified", "Reviewer One", "2026-10-18")  # fmt: skip
    assert data["acts"]["231"]["in_force"] == "verified" and not manual
    assert jury_blockers(Rulebook.model_validate(data), "W-NO-PERSONAL-ITEMS") == []


def test_ambiguous_answers_go_to_a_person():
    reviews = [
        _review("231-20-2", quote="differs", corrected_punkt="п. 20 ч. 3",
                rules={"L-NO-CASH-ON-LEAVE": "no_support"}),
        _review("231-22", reviewer="u_unknown"),
    ]  # fmt: skip
    data, applied, manual = apply_reviews(copy.deepcopy(DATA), reviews, NAMES)
    assert data["norms"]["231-20-2"]["citation_status"] == "pending"
    assert data["norms"]["231-22"]["citation_status"] == "pending"  # no name for the reviewer
    assert "L-NO-CASH-ON-LEAVE" in data["rules"] and not applied
    assert len(manual) == 4


def test_repealed_act_and_missing_clause():
    reviews = [_review("53-71-9", in_force="no"), _review("231-7", quote="not_found")]
    data, applied, _ = apply_reviews(copy.deepcopy(DATA), reviews, NAMES)
    assert data["acts"]["53"]["in_force"] == "repealed"
    assert data["norms"]["231-7"]["citation_status"] == "invalid"


def test_strength_change_is_applied_and_validated():
    data, applied, _ = apply_reviews(
        copy.deepcopy(DATA), [_review("231-20-2b", rules={"S-SAFE-CLOSED": "indirect"})], NAMES
    )
    assert data["rules"]["S-SAFE-CLOSED"]["norms"]["231-20-2b"] == "indirect"
    with pytest.raises(ValueError):
        apply_reviews(copy.deepcopy(DATA), [_review("231-20-2b", rules={"S-SAFE-CLOSED": "maybe"})],
                      NAMES)  # fmt: skip


def test_header_comment_survives():
    assert _header(RULEBOOK.read_text(encoding="utf-8")).startswith("# The rulebook")
