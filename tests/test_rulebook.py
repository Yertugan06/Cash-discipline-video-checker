"""The rulebook (`knowledge/rulebook.yaml`) is the one source for rules and their legal basis;
`scripts/build_knowledge.py` generates the Knowledge Pack and the F1 codex rules from it."""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from scripts.build_knowledge import (
    F1_CODEX,
    RULEBOOK,
    Rulebook,
    freeze_problems,
    load_rulebook,
    render,
    validate_outputs,
)


@pytest.fixture(scope="module")
def raw() -> dict:
    return yaml.safe_load(RULEBOOK.read_text(encoding="utf-8"))


def _current_f1() -> dict:
    return yaml.safe_load(F1_CODEX.read_text(encoding="utf-8"))


def test_generated_files_are_up_to_date():
    files = render(load_rulebook(), _current_f1())
    stale = [str(p) for p, text in files.items() if p.read_text(encoding="utf-8") != text]
    assert not stale, f"stale: {stale}; run .venv/bin/python scripts/build_knowledge.py"


def test_generated_files_pass_the_service_loaders():
    validate_outputs(render(load_rulebook(), _current_f1()))


def test_f1_codex_keeps_everything_but_rules_and_clip_labels():
    current = _current_f1()
    generated = yaml.safe_load(
        render(load_rulebook(), {**current, "clips": [{"id": "X-1"}]})[F1_CODEX]
    )
    assert "clips" not in generated
    assert {k: v for k, v in generated.items() if k != "rules"} == {
        k: v for k, v in current.items() if k != "rules"
    }


def test_f1_citation_comes_from_the_rulebook(raw):
    rb = load_rulebook()
    f1 = {r["id"]: r for r in yaml.safe_load(render(rb, _current_f1())[F1_CODEX])["rules"]}
    for rule_id, rule in rb.rules.items():
        if rule.norms:
            primary = next(iter(rule.norms))
            assert f1[rule_id]["source_url"] == str(rb.norms[primary].url)
        else:
            assert f1[rule_id]["source"].startswith("не проверено:")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["rules"]["L-NO-CASH-ON-LEAVE"]["norms"].update({"999-1": "direct"}),
         "unknown norms"),
        (lambda d: d["norms"]["231-22"].update({"citation_status": "verified"}),
         "verified_by and verified_at"),
        (lambda d: d["norms"]["231-22"].update({"act": "48"}), "unknown act"),
        (lambda d: d["rules"]["L-NO-CASH-ON-LEAVE"].update({"norms": {}}),
         "needs an unverified_reference"),
        (lambda d: d["rules"]["L-NO-CASH-ON-LEAVE"].update({"mechanism": "x"}), "Extra inputs"),
    ],
)  # fmt: skip
def test_rulebook_rejects_broken_references(raw, mutate, message):
    data = copy.deepcopy(raw)
    mutate(data)
    with pytest.raises(ValidationError, match=message):
        Rulebook.model_validate(data)


def test_service_loaders_reject_an_enabled_unimplemented_rule(raw):
    data = copy.deepcopy(raw)
    data["rules"]["L-NO-CASH-ON-LEAVE"]["implementation_status"] = "unimplemented"
    with pytest.raises(ValueError, match="unimplemented"):
        validate_outputs(render(Rulebook.model_validate(data), _current_f1()))


def test_freeze_needs_verified_norms_and_acts_in_force(raw):
    data = copy.deepcopy(raw)
    for rule_id, rule in data["rules"].items():
        rule["enabled"] = rule_id == "W-NO-PERSONAL-ITEMS"
    rb = Rulebook.model_validate(data)
    assert freeze_problems(rb) == [
        "W-NO-PERSONAL-ITEMS: act 231 in force is unverified",
        "W-NO-PERSONAL-ITEMS: norm 231-12-1 is pending",
    ]
    data["acts"]["231"]["in_force"] = "verified"
    data["norms"]["231-12-1"].update(
        citation_status="verified", verified_by="reviewer", verified_at="2026-10-18"
    )
    assert freeze_problems(Rulebook.model_validate(data)) == []
