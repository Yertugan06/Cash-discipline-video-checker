"""Runtime Knowledge Pack loader: ``knowledge/rules.yaml`` + ``knowledge/norms.json`` -> grounded
findings and jury-facing descriptions.

This module never reads ``codex_verified.json`` or ``config/f1_codex.yaml`` -- those are build-time
inputs consumed only by ``scripts/build_knowledge.py``. ``describe()`` is the single place template
slots get filled in; nothing else in the codebase formats a ``RuleEntry.description_template``.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from backend.contracts import Finding, GroundedFinding, NormRef, RuleEntry, RuleScope

NOT_JURY_ELIGIBLE = "Not jury-eligible: its legal basis is not human-verified yet."


class KnowledgeError(ValueError):
    """Raised on any structural or referential problem in the Knowledge Pack."""


class Knowledge:
    def __init__(self, rules: list[RuleEntry], norms: dict[str, NormRef]) -> None:
        self._rules = rules
        self._by_id = {r.rule_id: r for r in rules}
        self._norms = norms

    @classmethod
    def load(cls, root: Path, scope: RuleScope = "detector") -> Knowledge:
        """`scope="jury"` reports only jury-eligible rules: every other enabled rule is loaded as
        disabled, so its citations can never reach the jury as if they had been verified."""
        rules_path = root / "rules.yaml"
        norms_path = root / "norms.json"

        try:
            raw_rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise KnowledgeError(f"cannot read {rules_path}: {exc}") from exc
        try:
            raw_norms = json.loads(norms_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KnowledgeError(f"cannot read {norms_path}: {exc}") from exc

        if not isinstance(raw_rules, list):
            raise KnowledgeError(f"{rules_path}: expected a list of rules")
        if not isinstance(raw_norms, list):
            raise KnowledgeError(f"{norms_path}: expected a list of norms")

        rules: list[RuleEntry] = []
        seen_rule_ids: set[str] = set()
        for entry in raw_rules:
            try:
                rule = RuleEntry.model_validate(entry)
            except ValidationError as exc:
                raise KnowledgeError(f"{rules_path}: invalid rule entry {entry!r}: {exc}") from exc
            if rule.rule_id in seen_rule_ids:
                raise KnowledgeError(f"{rules_path}: duplicate rule_id {rule.rule_id!r}")
            seen_rule_ids.add(rule.rule_id)
            rules.append(rule)

        norms: dict[str, NormRef] = {}
        for entry in raw_norms:
            try:
                norm = NormRef.model_validate(entry)
            except ValidationError as exc:
                raise KnowledgeError(f"{norms_path}: invalid norm entry {entry!r}: {exc}") from exc
            if norm.norm_id in norms:
                raise KnowledgeError(f"{norms_path}: duplicate norm_id {norm.norm_id!r}")
            norms[norm.norm_id] = norm

        for rule in rules:
            if rule.enabled and rule.business_status != "confirmed":
                raise KnowledgeError(f"enabled rule {rule.rule_id!r} is not business-confirmed")
            if rule.enabled and rule.implementation_status != "implemented":
                raise KnowledgeError(f"enabled rule {rule.rule_id!r} is marked unimplemented")
            if not rule.enabled and not rule.disabled_reason:
                raise KnowledgeError(f"disabled rule {rule.rule_id!r} needs a disabled_reason")
            if rule.enabled and not rule.norm_ids:
                raise KnowledgeError(f"enabled rule {rule.rule_id!r} has no norm_ids")
            if set(rule.citation_strengths) != set(rule.norm_ids):
                raise KnowledgeError(
                    f"rule {rule.rule_id!r} citation_strengths must cover every norm_id exactly"
                )
            for norm_id in rule.norm_ids:
                if norm_id not in norms:
                    raise KnowledgeError(
                        f"rule {rule.rule_id!r} references unknown norm {norm_id!r}"
                    )
                if rule.enabled and norms[norm_id].citation_status == "invalid":
                    raise KnowledgeError(
                        f"enabled rule {rule.rule_id!r} uses invalid citation {norm_id!r}"
                    )
            if rule.jury_eligible and not (
                rule.enabled
                and rule.norm_ids
                and all(norms[n].citation_status == "verified" for n in rule.norm_ids)
            ):
                raise KnowledgeError(
                    f"rule {rule.rule_id!r} is jury_eligible without enabled, verified citations"
                )

        if scope == "jury":
            rules = [
                r
                if r.jury_eligible or not r.enabled
                else r.model_copy(update={"enabled": False, "disabled_reason": NOT_JURY_ELIGIBLE})
                for r in rules
            ]
            if not any(r.enabled for r in rules):
                raise KnowledgeError(
                    "RULE_SCOPE=jury but no rule is jury-eligible: verify the norms in "
                    "knowledge/rulebook.yaml, or set RULE_SCOPE=detector for experiments"
                )
        elif scope != "detector":
            raise KnowledgeError(f"unknown rule scope {scope!r}")

        return cls(rules, norms)

    @property
    def rules(self) -> list[RuleEntry]:
        return list(self._rules)

    def enabled_rules(self) -> list[RuleEntry]:
        return [r for r in self._rules if r.enabled]

    def rule(self, rule_id: str) -> RuleEntry:
        try:
            return self._by_id[rule_id]
        except KeyError:
            raise KnowledgeError(f"unknown rule_id {rule_id!r}") from None

    def norm(self, norm_id: str) -> NormRef:
        """Additive helper (not in the frozen WP3 interface list, but harmless to consumers):
        look up a single norm by id, e.g. for doc rendering."""
        try:
            return self._norms[norm_id]
        except KeyError:
            raise KnowledgeError(f"unknown norm_id {norm_id!r}") from None

    def ground(self, findings: list[Finding]) -> list[GroundedFinding]:
        grounded: list[GroundedFinding] = []
        for finding in findings:
            rule = self.rule(finding.rule_id)
            norms = [self._norms[nid] for nid in rule.norm_ids]
            if any(n.citation_status == "invalid" for n in norms):
                citation_status = "invalid"
            elif norms and all(n.citation_status == "verified" for n in norms):
                citation_status = "verified"
            else:
                citation_status = "pending"
            grounded.append(
                GroundedFinding(
                    finding=finding, rule=rule, norms=norms, citation_status=citation_status
                )
            )
        return grounded

    def describe(self, g: GroundedFinding) -> str:
        """The jury ``description``: the observation (facts filled into the template), then the
        claim. Citation (act/punkt/quote/URL/status) is reported separately via ``GroundedFinding``
        and never inlined here."""
        facts = dict(g.finding.facts)
        facts.setdefault("t", round(g.finding.t_anchor, 1))
        try:
            observation = g.rule.description_template.format(**facts)
        except (KeyError, IndexError) as exc:
            raise KnowledgeError(
                f"description_template for {g.rule.rule_id!r} needs a fact missing from "
                f"Finding.facts: {exc}"
            ) from exc
        claim = f"Признаки возможного нарушения: {g.rule.title_ru}."
        return f"{observation} {claim}"
