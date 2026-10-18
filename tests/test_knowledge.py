"""Unit tests for `backend.knowledge.Knowledge`: loading, grounding, citation status, describe(),
and the generated docs/RULES.md staying in sync."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from backend.contracts import Finding
from backend.knowledge import Knowledge, KnowledgeError

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_ROOT = ROOT / "knowledge"


def _write_pack(tmp_path: Path, rules: list[dict], norms: list[dict]) -> Path:
    rules_yaml = yaml.safe_dump(rules, allow_unicode=True)
    (tmp_path / "rules.yaml").write_text(rules_yaml, encoding="utf-8")
    (tmp_path / "norms.json").write_text(json.dumps(norms), encoding="utf-8")
    return tmp_path


def _norm(norm_id: str, citation_status: str = "pending") -> dict:
    return {
        "norm_id": norm_id,
        "jurisdiction": "KZ",
        "document_title": "Test regulation",
        "issuing_authority": "Test authority",
        "act": "1",
        "act_number": "1",
        "adopted_on": "2026-01-01",
        "punkt": "п. 1",
        "quote": "quote",
        "url": "https://adilet.zan.kz/rus/docs/V0000000001#z1",
        "citation_status": citation_status,
        "verified_by": "jane" if citation_status == "verified" else None,
        "verified_at": "2026-01-01" if citation_status == "verified" else None,
    }


def _simple_finding(rule_id: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        t_anchor=1.0,
        t_start=1.0,
        t_end=1.0,
        support_t=[1.0],
        facts={},
        rank_score=1.0,
    )


def _rule(rule_id: str, norm_ids: list[str], enabled: bool = True, template: str = "t={t}") -> dict:
    return {
        "rule_id": rule_id,
        "business_status": "confirmed",
        "implementation_status": "implemented",
        "title_ru": f"{rule_id}-ru",
        "title_en": f"{rule_id}-en",
        "mechanism": "m",
        "states_used": [],
        "params": {},
        "description_template": template,
        "visibility_caveat": "v",
        "norm_ids": norm_ids,
        "citation_strengths": {norm_id: "direct" for norm_id in norm_ids},
        "enabled": enabled,
        "disabled_reason": None if enabled else "Disabled for test.",
    }


# ---------------------------------------------------------------------------------------------
# Loading the real, checked-in Knowledge Pack.
# ---------------------------------------------------------------------------------------------


def test_real_pack_loads_and_every_enabled_rule_has_a_norm():
    k = Knowledge.load(KNOWLEDGE_ROOT)
    assert len(k.rules) > 0
    for rule in k.enabled_rules():
        assert rule.norm_ids, f"{rule.rule_id} is enabled but has no norms"
        for norm_id in rule.norm_ids:
            assert k.norm(norm_id) is not None


def test_real_pack_citations_are_pending_until_human_review():
    """An AI must never mark a citation verified (AGENTS.md rule 6); this is the current,
    honest state of the pack until a human does the adilet.zan.kz pass."""
    k = Knowledge.load(KNOWLEDGE_ROOT)
    for rule in k.rules:
        for norm_id in rule.norm_ids:
            assert k.norm(norm_id).citation_status == "pending"


# ---------------------------------------------------------------------------------------------
# Loader failures.
# ---------------------------------------------------------------------------------------------


def test_unknown_norm_id_fails_to_load(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", ["missing-norm"])], [])
    with pytest.raises(KnowledgeError, match="unknown norm"):
        Knowledge.load(pack)


def test_enabled_rule_without_norms_fails_to_load(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", [], enabled=True)], [])
    with pytest.raises(KnowledgeError, match="no norm_ids"):
        Knowledge.load(pack)


def test_disabled_rule_without_norms_is_allowed(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", [], enabled=False)], [])
    k = Knowledge.load(pack)
    assert k.rule("R1").enabled is False


def test_duplicate_rule_id_fails_to_load(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", ["n1"]), _rule("R1", ["n1"])], [_norm("n1")])
    with pytest.raises(KnowledgeError, match="duplicate rule_id"):
        Knowledge.load(pack)


def test_duplicate_norm_id_fails_to_load(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", ["n1"])], [_norm("n1"), _norm("n1")])
    with pytest.raises(KnowledgeError, match="duplicate norm_id"):
        Knowledge.load(pack)


def test_malformed_rule_entry_fails_to_load(tmp_path):
    bad_rule = _rule("R1", ["n1"])
    del bad_rule["title_ru"]
    pack = _write_pack(tmp_path, [bad_rule], [_norm("n1")])
    with pytest.raises(KnowledgeError):
        Knowledge.load(pack)


def test_unknown_rule_id_lookup_raises():
    k = Knowledge.load(KNOWLEDGE_ROOT)
    with pytest.raises(KnowledgeError, match="unknown rule_id"):
        k.rule("NOT-A-RULE")


# ---------------------------------------------------------------------------------------------
# citation_status.
# ---------------------------------------------------------------------------------------------


def test_citation_status_pending_when_norm_unverified(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", ["n1"])], [_norm("n1", "pending")])
    k = Knowledge.load(pack)
    finding = _simple_finding("R1")
    grounded = k.ground([finding])
    assert grounded[0].citation_status == "pending"


def test_citation_status_verified_only_if_every_norm_is_verified(tmp_path):
    pack = _write_pack(
        tmp_path,
        [_rule("R1", ["n1", "n2"])],
        [_norm("n1", "verified"), _norm("n2", "pending")],
    )
    k = Knowledge.load(pack)
    finding = _simple_finding("R1")
    assert k.ground([finding])[0].citation_status == "pending"

    all_verified_dir = tmp_path / "all_verified"
    all_verified_dir.mkdir()
    pack2 = _write_pack(
        all_verified_dir,
        [_rule("R1", ["n1", "n2"])],
        [_norm("n1", "verified"), _norm("n2", "verified")],
    )
    k2 = Knowledge.load(pack2)
    assert k2.ground([finding])[0].citation_status == "verified"


def test_invalid_norm_propagates_invalid_citation_status(tmp_path):
    pack = _write_pack(
        tmp_path,
        [_rule("R1", ["n1"], enabled=False)],
        [_norm("n1", "invalid")],
    )
    k = Knowledge.load(pack)
    assert k.ground([_simple_finding("R1")])[0].citation_status == "invalid"


def test_enabled_rule_rejects_invalid_citation_at_load(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", ["n1"])], [_norm("n1", "invalid")])
    with pytest.raises(KnowledgeError, match="invalid citation"):
        Knowledge.load(pack)


# ---------------------------------------------------------------------------------------------
# describe().
# ---------------------------------------------------------------------------------------------


def test_describe_contains_observation_and_claim(tmp_path):
    template = "С {t_start} по {t_end} с кассир отсутствует; на столе видны {object}."
    pack = _write_pack(tmp_path, [_rule("R1", ["n1"], template=template)], [_norm("n1")])
    k = Knowledge.load(pack)
    finding = Finding(
        rule_id="R1",
        t_anchor=5.0,
        t_start=5.0,
        t_end=9.0,
        support_t=[5.0, 6.0, 7.0],
        facts={"t_start": 5.0, "t_end": 9.0, "object": "наличные"},
        rank_score=3.0,
    )
    g = k.ground([finding])[0]
    text = k.describe(g)
    assert "с 5" in text.lower() or "5.0" in text  # the observation's time slots were filled
    assert "наличные" in text  # a fact slot was filled
    assert "Признаки возможного нарушения: R1-ru." in text  # the claim


def test_describe_raises_knowledge_error_on_missing_fact(tmp_path):
    pack = _write_pack(tmp_path, [_rule("R1", ["n1"], template="{missing_fact}")], [_norm("n1")])
    k = Knowledge.load(pack)
    finding = _simple_finding("R1")
    g = k.ground([finding])[0]
    with pytest.raises(KnowledgeError):
        k.describe(g)


# ---------------------------------------------------------------------------------------------
# docs/RULES.md stays in sync with the Knowledge Pack.
# ---------------------------------------------------------------------------------------------


def test_docs_rules_md_is_in_sync_with_knowledge_pack():
    from scripts.render_rules_doc import render

    k = Knowledge.load(KNOWLEDGE_ROOT)
    expected = render(k)
    actual = (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")
    assert actual == expected, "docs/RULES.md is stale; re-run scripts/render_rules_doc.py"


def test_docs_violation_types_md_is_in_sync_with_knowledge_pack():
    from scripts.render_rules_doc import render_types

    expected = render_types(Knowledge.load(KNOWLEDGE_ROOT))
    actual = (ROOT / "docs" / "VIOLATION_TYPES.md").read_text(encoding="utf-8")
    assert actual == expected, (
        "docs/VIOLATION_TYPES.md is stale; re-run scripts/render_rules_doc.py"
    )
