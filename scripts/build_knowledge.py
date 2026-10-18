"""Generate everything rule-related from the rulebook (`knowledge/rulebook.yaml`, the one source):

  knowledge/rules.yaml, knowledge/norms.json   the runtime Knowledge Pack
  config/f1_codex.yaml (`rules` only)          F1 thresholds and templates; other keys are kept
                                               (except per-clip labels, which never ship)

The generated files are validated by the same loaders the service uses at startup
(`backend.knowledge.Knowledge`, `backend.f1.codex.load_codex`), so a rulebook the service would
reject is never written.

    .venv/bin/python scripts/build_knowledge.py            # regenerate
    .venv/bin/python scripts/build_knowledge.py --check    # fail if a generated file is stale
    .venv/bin/python scripts/build_knowledge.py --freeze   # also fail unless every enabled rule
                                                           # rests on human-verified law
Then re-render `docs/RULES.md` with `scripts/render_rules_doc.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.f1.codex import Codex, Rule, load_codex  # noqa: E402
from backend.knowledge import Knowledge  # noqa: E402

RULEBOOK = ROOT / "knowledge" / "rulebook.yaml"
KNOWLEDGE_DIR = ROOT / "knowledge"
F1_CODEX = ROOT / "config" / "f1_codex.yaml"

Strength = Literal["direct", "indirect", "weak"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Act(_Strict):
    document_title: str
    issuing_authority: str
    adopted_on: date
    jurisdiction: Literal["KZ"]
    in_force: Literal["verified", "repealed", "unverified"]


class Norm(_Strict):
    act: str
    punkt: str
    quote: str = Field(min_length=1)
    url: HttpUrl
    citation_status: Literal["verified", "pending", "invalid"]
    verified_by: str | None
    verified_at: date | None

    @model_validator(mode="after")
    def _verified_has_who_and_when(self) -> Norm:
        if self.citation_status == "verified" and not (self.verified_by and self.verified_at):
            raise ValueError("a verified norm needs verified_by and verified_at")
        return self


class UnverifiedReference(_Strict):
    text: str
    url: HttpUrl
    strength: Strength


class F1Fields(_Strict):
    family: str
    signals: str
    min_duration_text: str
    min_duration_sec: float | None
    timecode_anchor: str
    title: str
    description_template: str
    title_en: str
    description_template_en: str


class RuleSpec(_Strict):
    type_ru: str
    type_en: str
    requirement: str
    visible_breach: str
    not_visible: str
    norms: dict[str, Strength]  # first entry = primary citation
    unverified_reference: UnverifiedReference | None = None
    business_status: Literal["confirmed", "candidate"]
    implementation_status: Literal["implemented", "unimplemented"]
    enabled: bool
    disabled_reason: str | None
    condition: str
    states_used: list[str]
    params: dict[str, float]
    description_template: str
    f1: F1Fields

    @model_validator(mode="after")
    def _reference_only_without_norms(self) -> RuleSpec:
        if self.norms and self.unverified_reference:
            raise ValueError("unverified_reference is only for rules with no norm")
        if not self.norms and not self.unverified_reference:
            raise ValueError("a rule with no norm needs an unverified_reference")
        return self


class Rulebook(_Strict):
    version: Literal[1]
    acts: dict[str, Act]
    norms: dict[str, Norm]
    rules: dict[str, RuleSpec]

    @model_validator(mode="after")
    def _references_resolve(self) -> Rulebook:
        for norm_id, norm in self.norms.items():
            if norm.act not in self.acts:
                raise ValueError(f"norm {norm_id} names unknown act {norm.act!r}")
        for rule_id, rule in self.rules.items():
            if unknown := [n for n in rule.norms if n not in self.norms]:
                raise ValueError(f"rule {rule_id} cites unknown norms {unknown}")
        return self


def load_rulebook(path: Path = RULEBOOK) -> Rulebook:
    return Rulebook.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# ---- generated files ---------------------------------------------------------------------------


def knowledge_pack(rb: Rulebook) -> tuple[list[dict], list[dict]]:
    """(rules.yaml rows, norms.json rows) in the runtime's schema."""
    rules = [
        {
            "rule_id": rule_id,
            "business_status": r.business_status,
            "implementation_status": r.implementation_status,
            "title_ru": r.type_ru,
            "title_en": r.type_en,
            "mechanism": r.condition,
            "states_used": r.states_used,
            "params": r.params,
            "description_template": r.description_template,
            "visibility_caveat": r.not_visible,
            "norm_ids": list(r.norms),
            "citation_strengths": dict(r.norms),
            "enabled": r.enabled,
            "disabled_reason": r.disabled_reason,
            "jury_eligible": not jury_blockers(rb, rule_id),
        }
        for rule_id, r in rb.rules.items()
    ]
    cited = list(dict.fromkeys(n for r in rb.rules.values() for n in r.norms))
    norms = []
    for norm_id in cited:
        norm, act = rb.norms[norm_id], rb.acts[rb.norms[norm_id].act]
        norms.append(
            {
                "norm_id": norm_id,
                "jurisdiction": act.jurisdiction,
                "document_title": act.document_title,
                "issuing_authority": act.issuing_authority,
                "adopted_on": act.adopted_on.isoformat(),
                "act": norm.act,
                "act_number": norm.act,
                "punkt": norm.punkt,
                "quote": norm.quote,
                "url": str(norm.url),
                "citation_status": norm.citation_status,
                "verified_by": norm.verified_by,
                "verified_at": norm.verified_at.isoformat() if norm.verified_at else None,
            }
        )
    return rules, norms


def _f1_rule(rb: Rulebook, rule_id: str, r: RuleSpec) -> Rule:
    if r.norms:
        primary = rb.norms[next(iter(r.norms))]
        source = "; ".join(
            f"Постановление № {rb.norms[n].act}, {rb.norms[n].punkt}" for n in r.norms
        )
        source_url, strength = str(primary.url), next(iter(r.norms.values()))
    else:
        ref = r.unverified_reference
        source, source_url, strength = f"не проверено: {ref.text}", str(ref.url), ref.strength
    return Rule(
        id=rule_id,
        family=r.f1.family,
        requirement=r.requirement,
        breach_condition=r.visible_breach,
        signals=r.f1.signals,
        min_duration_text=r.f1.min_duration_text,
        min_duration_sec=r.f1.min_duration_sec,
        timecode_anchor=r.f1.timecode_anchor,
        source=source,
        source_url=source_url,
        strength=strength.capitalize(),
        status=r.business_status.capitalize(),
        title=r.f1.title,
        description_template=r.f1.description_template,
        title_en=r.f1.title_en,
        description_template_en=r.f1.description_template_en,
    )


def f1_codex(rb: Rulebook, current: dict) -> Codex:
    """The F1 codex with its `rules` regenerated and every other key kept as it is. Per-clip label
    data (`clips`) is never carried into this runtime file."""
    rules = [_f1_rule(rb, rule_id, r) for rule_id, r in rb.rules.items()]
    kept = {k: v for k, v in current.items() if k != "clips"}
    return Codex.model_validate({**kept, "rules": [rule.model_dump() for rule in rules]})


def render(rb: Rulebook, current_f1: dict) -> dict[Path, str]:
    rules, norms = knowledge_pack(rb)
    return {
        KNOWLEDGE_DIR / "rules.yaml": yaml.safe_dump(
            rules, allow_unicode=True, sort_keys=False, width=100
        ),
        KNOWLEDGE_DIR / "norms.json": json.dumps(norms, ensure_ascii=False, indent=2) + "\n",
        F1_CODEX: yaml.safe_dump(
            f1_codex(rb, current_f1).model_dump(), allow_unicode=True, sort_keys=False
        ),
    }


def validate_outputs(files: dict[Path, str]) -> None:
    """Load the generated files with the service's own loaders; raises what startup would."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for path, text in files.items():
            (tmp_dir / path.name).write_text(text, encoding="utf-8")
        Knowledge.load(tmp_dir)
        load_codex(tmp_dir / F1_CODEX.name)


def jury_blockers(rb: Rulebook, rule_id: str) -> list[str]:
    """Why a rule may not be reported to the jury (Q32): it must be enabled and rest only on
    human-verified norms from acts confirmed in force (task.md §9, criterion 4)."""
    rule = rb.rules[rule_id]
    if not rule.enabled:
        return [f"{rule_id}: disabled"]
    if not rule.norms:
        return [f"{rule_id}: cites no norm"]
    blockers = []
    for norm_id in rule.norms:
        norm = rb.norms[norm_id]
        if norm.citation_status != "verified":
            blockers.append(f"{rule_id}: norm {norm_id} is {norm.citation_status}")
        if rb.acts[norm.act].in_force != "verified":
            blockers.append(f"{rule_id}: act {norm.act} in force is {rb.acts[norm.act].in_force}")
    return sorted(set(blockers))


def freeze_problems(rb: Rulebook) -> list[str]:
    """Blockers of every enabled rule: the submission needs none (`--freeze`)."""
    return sorted(
        b for rule_id, r in rb.rules.items() if r.enabled for b in jury_blockers(rb, rule_id)
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="write nothing; fail if a file is stale")
    ap.add_argument("--freeze", action="store_true", help="fail unless enabled law is verified")
    args = ap.parse_args(argv)

    rb = load_rulebook()
    files = render(rb, yaml.safe_load(F1_CODEX.read_text(encoding="utf-8")))
    validate_outputs(files)

    ok = True
    stale = [p for p, text in files.items() if p.read_text(encoding="utf-8") != text]
    if args.check:
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)} (run scripts/build_knowledge.py)", file=sys.stderr)
        ok = not stale
    else:
        for p in stale:
            p.write_text(files[p], encoding="utf-8")
            print(f"wrote {p.relative_to(ROOT)}")

    problems = freeze_problems(rb)
    enabled = [rule_id for rule_id, r in rb.rules.items() if r.enabled]
    eligible = [rule_id for rule_id in enabled if not jury_blockers(rb, rule_id)]
    print(
        f"{len(rb.rules)} rules: {len(enabled)} detector-enabled, {len(eligible)} jury-eligible; "
        f"{len(problems)} blocker(s) on enabled rules"
    )
    if args.freeze:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        ok &= not problems
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
