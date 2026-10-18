"""The legal catalog (`scripts/build_legal_catalog.py`) checks every rulebook citation against the
stored text of the act, so a quote that is not in the law, or sits in another punkt, fails here."""

from __future__ import annotations

import pytest

from scripts import build_legal_catalog as catalog
from scripts.build_knowledge import load_rulebook


@pytest.fixture(scope="module")
def built() -> dict:
    return catalog.build()


@pytest.fixture(scope="module")
def punkts() -> dict:
    found = {}
    for act in ("231", "14", "53"):
        lines = catalog.clean_lines(catalog.docx_lines(catalog.SOURCES / act / "source.docx"))
        found.update({p.id: p for p in catalog.segment(act, lines)})
    return found


def test_generated_files_are_up_to_date(built):
    stale = [
        str(p)
        for p, text in built.items()
        if not p.exists() or p.read_text(encoding="utf-8") != text
    ]
    assert not stale, f"stale: {stale}; run .venv/bin/python scripts/build_legal_catalog.py"


def test_every_punkt_of_each_act_is_segmented(punkts):
    counts = {act: sum(1 for p in punkts.values() if p.act == act) for act in ("231", "14", "53")}
    # 231: 133 punkts plus 21 inserted by amendments (10-1, 53-1, 63-1..6, 87-1, 90-1, 109-1..11)
    assert counts == {"231": 154, "14": 24, "53": 162}
    assert punkts["231-53-1"].text.startswith("53-1. Допускается упаковывать")
    assert not any("53-1." in part for part in punkts["231-53"].parts)
    assert punkts["231-22"].text == (
        "22. Кассовому работнику не допускается покидать рабочее место "
        "до окончания обслуживания клиента."
    )
    assert punkts["231-20"].parts[1].startswith("На рабочем месте кассового работника")
    assert [n for n, _, _ in punkts["231-19"].subpunkts] == [1, 2, 3, 4, 5, 6]


def test_every_rulebook_quote_is_verbatim_in_the_cited_unit(built, punkts):
    rulebook = load_rulebook()
    acts = set(catalog.SOURCES_META["acts"])
    repealed = catalog.SOURCES_META["repealed"]
    failures = {
        norm_id: result
        for norm_id, norm in rulebook.norms.items()
        if (result := catalog.check_norm(punkts, acts, repealed, norm))["result"]
        != "quote_in_cited_unit"
    }
    assert not failures


def _norm(**changes):
    norm = load_rulebook().norms["231-22"]
    return norm.model_copy(update=changes)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"quote": "Кассовому работнику разрешается покидать рабочее место"}, "quote_not_found"),
        ({"punkt": "п. 21"}, "quote_in_other_unit"),
        ({"act": "48"}, "repealed_act"),
        ({"act": "99"}, "no_source_text"),
    ],
)
def test_a_wrong_citation_is_caught(built, punkts, changes, expected):
    acts = set(catalog.SOURCES_META["acts"])
    result = catalog.check_norm(punkts, acts, catalog.SOURCES_META["repealed"], _norm(**changes))
    assert result["result"] == expected


def test_every_enabled_rule_has_an_f1_evaluator():
    rulebook = load_rulebook()
    capabilities = catalog.f1_capabilities()
    enabled = {rule_id for rule_id, rule in rulebook.rules.items() if rule.enabled}
    assert enabled <= set(capabilities)
    assert all(capabilities[rule_id]["events"] for rule_id in enabled)
