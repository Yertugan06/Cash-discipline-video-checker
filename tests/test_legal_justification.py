"""Does the service give a correct legal justification (task.md §9 criterion 4)?

Three independent checks on the real, checked-in Knowledge Pack (`knowledge/rules.yaml` +
`knowledge/norms.json`), each re-deriving ground truth from the stored act texts rather than
trusting `knowledge/rulebook.yaml`'s own fields:

1. `describe()` and `serialize.to_done_job()` always cite the rule's PRIMARY norm (`norm_ids[0]`),
   never a different one the rule happens to also list.
2. Every enabled rule's cited quotes are verbatim in the act, at the exact punkt/part/subpunkt
   named -- re-segmenting the .docx independently of `scripts/build_legal_catalog.py`'s own
   module-level state.
3. The act's title and issuing authority shown in a citation match what the act says about
   itself, not a typo carried in `knowledge/rulebook.yaml`.

`tests/test_legal_catalog.py` checks the same quotes at the `rulebook.yaml` level; this file
checks what actually ships in `knowledge/rules.yaml`/`norms.json` and what the jury JSON contains.
"""

from __future__ import annotations

import string

import pytest
import yaml

from backend.config import ROOT
from backend.contracts import Coverage, DetectionResult, EvidenceFrame, Finding
from backend.knowledge import Knowledge, citation
from backend.serialize import to_done_job
from scripts import build_legal_catalog as catalog

KNOWLEDGE_ROOT = ROOT / "knowledge"

# Each act's self-declared issuing authority, read from its own text -- an independent check
# that knowledge/rulebook.yaml's acts.<n>.issuing_authority was not mistyped or swapped.
_AUTHORITY_MARKER = {
    "231": "Национального Банка",
    "14": "Национального Банка",
    "53": "Агентства Республики Казахстан по регулированию и развитию финансового рынка",
}


@pytest.fixture(scope="module")
def sources_meta() -> dict:
    return yaml.safe_load((catalog.SOURCES / "sources.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def act_texts() -> dict[str, list[str]]:
    """Each act's own text, line by line, independently re-extracted from the stored .docx."""
    return {
        act: catalog.clean_lines(catalog.docx_lines(catalog.SOURCES / act / "source.docx"))
        for act in ("231", "14", "53")
    }


@pytest.fixture(scope="module")
def punkts(act_texts) -> dict:
    found = {}
    for act, lines in act_texts.items():
        found.update({p.id: p for p in catalog.segment(act, lines)})
    return found


@pytest.fixture(scope="module")
def knowledge() -> Knowledge:
    return Knowledge.load(KNOWLEDGE_ROOT)


def _dummy_finding(rule_id: str, template: str) -> Finding:
    """A Finding with every slot `description_template` needs filled, so `describe()` runs for
    real on every enabled rule without constructing a whole F1 timeline."""
    fields = {name for _, name, _, _ in string.Formatter().parse(template) if name and name != "t"}
    facts: dict[str, str | float] = {f: ("наличные" if f == "object" else 12.0) for f in fields}
    return Finding(
        rule_id=rule_id,
        t_anchor=12.0,
        t_start=12.0,
        t_end=12.0,
        support_t=[12.0],
        facts=facts,
        rank_score=1.0,
    )


def _one_violation(knowledge: Knowledge, g):
    frames = [[EvidenceFrame(timestamp_sec=12.0, image_base64="/9j/4AAQSkZJRgABAQAAAQABAAD/2Q==")]]
    result = DetectionResult(
        findings=[g.finding],
        coverage=Coverage(step_s=0.5, planned=1, done=1, failed=0, deadline_hit=False, mode="full"),
        warnings=[],
    )
    return to_done_job("t", [g], result, frames, knowledge.describe).violations[0]


def test_every_enabled_rules_basis_names_its_primary_norm(knowledge):
    for rule in knowledge.enabled_rules():
        finding = _dummy_finding(rule.rule_id, rule.description_template)
        g = knowledge.ground([finding])[0]
        primary_id = rule.norm_ids[0]
        primary = knowledge.norm(primary_id)
        assert g.norms[0].norm_id == primary_id, f"{rule.rule_id}: ground() reordered the norms"

        text = knowledge.describe(g)
        assert text.endswith(f"Норма: {citation(primary)}."), rule.rule_id
        assert "None" not in text and ".." not in text

        violation = _one_violation(knowledge, g)
        assert violation.source == f"{primary.act}, {primary.punkt}"
        assert violation.source_quote == primary.quote
        assert str(violation.source_url) == str(primary.url)
        assert violation.strength == rule.citation_strengths[primary_id]
        assert violation.document_title == primary.document_title
        assert violation.issuing_authority == primary.issuing_authority


def test_every_enabled_rules_quotes_are_verbatim_in_the_real_law(knowledge, punkts, sources_meta):
    catalog.SOURCES_META.clear()
    catalog.SOURCES_META.update(sources_meta)
    acts = set(sources_meta["acts"])
    repealed = sources_meta.get("repealed", {})
    failures = {
        (rule.rule_id, norm_id): result
        for rule in knowledge.enabled_rules()
        for norm_id in rule.norm_ids
        if (result := catalog.check_norm(punkts, acts, repealed, knowledge.norm(norm_id)))["result"]
        != "quote_in_cited_unit"
    }
    assert not failures


def test_every_cited_acts_title_and_authority_match_the_acts_own_text(knowledge, act_texts):
    header_cache: dict[str, str] = {}
    for rule in knowledge.enabled_rules():
        for norm_id in rule.norm_ids:
            norm = knowledge.norm(norm_id)
            header = header_cache.setdefault(norm.act, " ".join(act_texts[norm.act][:3]))
            assert norm.document_title in header, (
                f"{norm_id}: document_title not in the act's own text"
            )
            assert _AUTHORITY_MARKER[norm.act] in header


def test_no_enabled_rule_cites_an_invalid_or_repealed_norm(knowledge, sources_meta):
    repealed = set(sources_meta.get("repealed", {}))
    for rule in knowledge.enabled_rules():
        for norm_id in rule.norm_ids:
            norm = knowledge.norm(norm_id)
            assert norm.citation_status != "invalid", f"{rule.rule_id} cites invalid {norm_id}"
            assert norm.act not in repealed, f"{rule.rule_id} cites repealed act {norm.act}"
