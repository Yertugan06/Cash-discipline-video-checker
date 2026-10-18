"""RULE_SCOPE: technical experiments see every detector-enabled rule; the jury sees only rules
whose legal basis a person has verified (Q32)."""

from __future__ import annotations

import copy

import pytest
import yaml

from backend.config import Settings
from backend.knowledge import Knowledge, KnowledgeError
from scripts.build_knowledge import F1_CODEX, KNOWLEDGE_DIR, RULEBOOK, Rulebook, render


def _pack(tmp_path, verify: tuple[str, ...] = ()):
    data = yaml.safe_load(RULEBOOK.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    for rule_id in verify:
        rule = data["rules"][rule_id]
        for norm_id in rule["norms"]:
            data["norms"][norm_id].update(
                citation_status="verified", verified_by="reviewer", verified_at="2026-10-18"
            )
            data["acts"][data["norms"][norm_id]["act"]]["in_force"] = "verified"
    files = render(Rulebook.model_validate(data), yaml.safe_load(F1_CODEX.read_text("utf-8")))
    for path, text in files.items():
        if path.parent == KNOWLEDGE_DIR:
            (tmp_path / path.name).write_text(text, encoding="utf-8")
    return tmp_path


def test_jury_scope_reports_only_verified_rules(tmp_path):
    pack = _pack(tmp_path, verify=("W-NO-PERSONAL-ITEMS",))
    detector = Knowledge.load(pack, "detector")
    jury = Knowledge.load(pack, "jury")
    assert len(detector.enabled_rules()) == 15
    assert [r.rule_id for r in jury.enabled_rules()] == ["W-NO-PERSONAL-ITEMS"]
    demoted = jury.rule("L-NO-CASH-ON-LEAVE")
    assert not demoted.enabled and "not human-verified" in demoted.disabled_reason
    assert [r.rule_id for r in jury.rules] == [r.rule_id for r in detector.rules]  # F1 needs all


def test_jury_scope_refuses_to_start_with_nothing_verified():
    with pytest.raises(KnowledgeError, match="no rule is jury-eligible"):
        Knowledge.load(KNOWLEDGE_DIR, "jury")


def test_a_hand_edited_jury_flag_is_rejected(tmp_path):
    pack = _pack(tmp_path)
    rules = yaml.safe_load((pack / "rules.yaml").read_text("utf-8"))
    rules[0]["jury_eligible"] = True
    (pack / "rules.yaml").write_text(yaml.safe_dump(rules, allow_unicode=True), "utf-8")
    with pytest.raises(KnowledgeError, match="jury_eligible without enabled, verified"):
        Knowledge.load(pack)


def test_settings_default_to_the_jury_scope(monkeypatch):
    monkeypatch.delenv("RULE_SCOPE", raising=False)
    monkeypatch.setenv("API_KEY", "k")
    assert Settings.from_env().rule_scope == "jury"
    monkeypatch.setenv("RULE_SCOPE", "everything")
    with pytest.raises(ValueError, match="RULE_SCOPE"):
        Settings.from_env()
