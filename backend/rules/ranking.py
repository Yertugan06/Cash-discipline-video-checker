"""Ranking and capping of findings.

Default policy, frozen for dev: order by persistence (``Finding.rank_score``, descending), then
by the rule's position in ``knowledge/rules.yaml`` (ascending). For equal scores within the
same rule, prefer a confirmed exit over an unconfirmed absence, then cap to ``cap`` findings.
This is the *only* policy implemented here -- any dev-only tuning of the
ordering, and the one-time scoring of a tuned policy on the lockbox split, is a later
human-gated step (see ``knowledge/README.md``).
"""

from __future__ import annotations

from backend.contracts import Finding, RuleEntry


def rank(findings: list[Finding], rules: list[RuleEntry], cap: int = 3) -> list[Finding]:
    """Score, rule order, then corroborated exit for otherwise equal findings; capped."""
    order = {r.rule_id: i for i, r in enumerate(rules)}
    fallback = len(order)

    def key(f: Finding) -> tuple[float, int, bool]:
        confirmed = f.rule_id in order and f.facts.get("confirmed_exit") is True
        return (-f.rank_score, order.get(f.rule_id, fallback), not confirmed)

    return sorted(findings, key=key)[:cap]
