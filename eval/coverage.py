"""Rule coverage of the dataset: for every organizer-violation video, can the rulebook explain it?

Each human annotation's first norm is matched by clause (the scorer's own `code_match`) against
the rulebook's norms and the clause hints of rules that have none. Every violation video lands in
exactly one gap category, best first, so the report says *why* a video is not covered instead of
implying a missing rule:

  covered_verified        an enabled rule cites the clause and the norm is human-verified
  covered_pending         an enabled rule cites the clause; the norm is not verified yet
  rule_without_evaluator  only disabled rules cite it, and F1 has no evaluator for them
  rule_candidate          only disabled rules cite it, still business candidates
  rule_disabled_other     only disabled rules cite it, for another reason (observability, law)
  rule_without_norm       only a rule with an unverified reference points near it
  clause_not_in_rulebook  nothing in the rulebook cites the clause (missing rule or wrong mapping)
  annotation_unreliable   the human annotation is marked unreliable (team/reviews.json)
  no_annotation           no human annotation names a norm for this video

Prints counts and clip IDs only; details go to `<out>/coverage.json`.

    .venv/bin/python -m eval.coverage
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path

from backend.clip_id import clip_number
from eval.ground_truth import DEFAULT_OUT
from scripts.build_knowledge import Rulebook, load_rulebook

SCORE_UTILS = (
    Path(__file__).resolve().parent.parent
    / "validation"
    / "validation-evidence"
    / ("harness/score_utils.py")
)
ORDER = (
    "covered_verified",
    "covered_pending",
    "rule_without_evaluator",
    "rule_candidate",
    "rule_disabled_other",
    "rule_without_norm",
    "clause_not_in_rulebook",
    "annotation_unreliable",
    "no_annotation",
)


def _code_match():
    spec = importlib.util.spec_from_file_location("score_utils", SCORE_UTILS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.code_match


def classify(clause: str, rb: Rulebook, code_match) -> tuple[str, list[str]]:
    """Category for one annotated clause, and the rules behind that category."""
    citing = collections.defaultdict(list)  # category -> rule ids
    for rule_id, rule in rb.rules.items():
        if rule.norms:
            for norm_id in rule.norms:
                if not code_match(clause, rb.norms[norm_id].punkt):
                    continue
                if rule.enabled:
                    verified = rb.norms[norm_id].citation_status == "verified"
                    citing["covered_verified" if verified else "covered_pending"].append(rule_id)
                elif rule.implementation_status == "unimplemented":
                    citing["rule_without_evaluator"].append(rule_id)
                elif rule.business_status == "candidate":
                    citing["rule_candidate"].append(rule_id)
                else:
                    citing["rule_disabled_other"].append(rule_id)
        elif rule.unverified_reference:
            hint = rule.unverified_reference.text.split(",", 1)[-1]
            if code_match(clause, hint):
                citing["rule_without_norm"].append(rule_id)
    for category in ORDER:
        if citing[category]:
            return category, sorted(set(citing[category]))
    return "clause_not_in_rulebook", []


def coverage(gt: dict[str, dict], rb: Rulebook, code_match) -> dict[str, dict]:
    report = {}
    for key, video in gt.items():
        if not video["violation"]:
            continue
        clauses = [h["norm1"] for h in video["human"] if h.get("norm1")]
        if not clauses:
            report[key] = {"category": "no_annotation", "rules": []}
            continue
        best = min(
            (classify(c, rb, code_match) for c in clauses), key=lambda cr: ORDER.index(cr[0])
        )
        category = best[0]
        if not video["human_reliable"] and category not in ORDER[:2]:
            category = "annotation_unreliable"
        report[key] = {"category": category, "rules": best[1], "clauses": clauses}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    gt = json.loads((args.out / "gt.json").read_text(encoding="utf-8"))
    report = coverage(gt, load_rulebook(), _code_match())
    (args.out / "coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"violation videos {len(report)} -> {args.out / 'coverage.json'}")
    for category in ORDER:
        clips = sorted((k for k, v in report.items() if v["category"] == category), key=clip_number)
        if clips:
            print(f"  {category}: {len(clips)} ({', '.join(clips)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
