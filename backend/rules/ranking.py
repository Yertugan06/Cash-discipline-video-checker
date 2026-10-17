"""Ranking and capping of findings.

Default policy, frozen for dev: order by persistence (``Finding.rank_score``, descending), then
by the rule's position in ``knowledge/rules.yaml`` (ascending) as the tie-break, then cap to
``cap`` findings. This is the *only* policy implemented here -- any dev-only tuning of the
ordering, and the one-time scoring of a tuned policy on the lockbox split, is a later
human-gated step (see ``knowledge/README.md``).
"""

from __future__ import annotations

from backend.contracts import Finding, RuleEntry


def rank(findings: list[Finding], rules: list[RuleEntry], cap: int = 3) -> list[Finding]:
    """Persistence first (higher ``rank_score`` wins), then rule order in ``rules``, capped."""
    order = {r.rule_id: i for i, r in enumerate(rules)}
    fallback = len(order)

    def key(f: Finding) -> tuple[float, int]:
        return (-f.rank_score, order.get(f.rule_id, fallback))

    return sorted(findings, key=key)[:cap]
