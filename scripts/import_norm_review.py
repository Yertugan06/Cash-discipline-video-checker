"""Apply the legal reviewer's answers (the norm checklist) to `knowledge/rulebook.yaml`.

Input: a directory of review documents, one JSON per norm, as exported from the checklist's
`reviews` collection: {norm_id, quote, in_force, rules: {rule_id: direct|indirect|no_support},
corrected_punkt, note, reviewer, updated_at}; plus a JSON map {reviewer id: name}.

What is applied, and nothing else:
  quote=matches and in_force=yes  -> norm verified (verified_by, verified_at from the review);
                                     its act in_force=verified
  quote=not_found                 -> norm invalid
  in_force=no                     -> act repealed
  rules.<id> = direct | indirect  -> that rule's strength for this norm
What is reported for a person to apply by hand, never applied:
  quote=differs, a corrected clause, a note, rules.<id> = no_support (dropping a citation or
  disabling a rule is a decision, not an import).

    .venv/bin/python scripts/import_norm_review.py <reviews_dir> <names.json> [--write]
Then: scripts/build_knowledge.py && scripts/render_rules_doc.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_knowledge import RULEBOOK, Rulebook  # noqa: E402


def apply_reviews(
    data: dict, reviews: list[dict], names: dict[str, str]
) -> tuple[dict, list[str], list[str]]:
    """(updated rulebook data, changes applied, items for a person)."""
    applied, manual = [], []
    for review in sorted(reviews, key=lambda r: r["norm_id"]):
        norm_id = review["norm_id"]
        if norm_id not in data["norms"]:
            manual.append(f"{norm_id}: reviewed but not in the rulebook")
            continue
        norm = data["norms"][norm_id]
        who = names.get(review.get("reviewer") or "", "")
        when = (review.get("updated_at") or "")[:10]
        if review["quote"] == "matches" and review["in_force"] == "yes":
            if not (who and when):
                manual.append(f"{norm_id}: verified but reviewer name or date unknown")
            else:
                norm.update(citation_status="verified", verified_by=who, verified_at=when)
                data["acts"][norm["act"]]["in_force"] = "verified"
                applied.append(f"{norm_id}: verified by {who} on {when}")
        elif review["quote"] == "not_found":
            norm.update(
                citation_status="invalid", verified_by=who or None, verified_at=when or None
            )
            applied.append(f"{norm_id}: invalid (clause not found)")
        if review["in_force"] == "no":
            data["acts"][norm["act"]]["in_force"] = "repealed"
            applied.append(f"act {norm['act']}: repealed (from {norm_id})")
        if review["quote"] == "differs":
            manual.append(f"{norm_id}: quote differs from the current text; fix quote/punkt")
        if review.get("corrected_punkt"):
            manual.append(f"{norm_id}: reviewer gives the clause as {review['corrected_punkt']!r}")
        if review.get("note"):
            manual.append(f"{norm_id}: note: {review['note']}")
        for rule_id, verdict in (review.get("rules") or {}).items():
            rule = data["rules"].get(rule_id)
            if rule is None or norm_id not in rule["norms"]:
                manual.append(f"{norm_id}: verdict for {rule_id}, which does not cite it")
            elif verdict == "no_support":
                manual.append(f"{rule_id}: reviewer says {norm_id} does not support it")
            elif rule["norms"][norm_id] != verdict:
                applied.append(
                    f"{rule_id}: {norm_id} strength {rule['norms'][norm_id]} -> {verdict}"
                )
                rule["norms"][norm_id] = verdict
    Rulebook.model_validate(data)
    return data, applied, manual


def _header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(
        line for line in lines[: next(i for i, x in enumerate(lines) if not x.startswith("#"))]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("reviews", type=Path)
    ap.add_argument("names", type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    text = RULEBOOK.read_text(encoding="utf-8")
    reviews = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.reviews.glob("*.json"))
    ]
    names = json.loads(args.names.read_text(encoding="utf-8"))
    data, applied, manual = apply_reviews(yaml.safe_load(text), reviews, names)
    print(f"{len(reviews)} review(s): {len(applied)} change(s), {len(manual)} item(s) for a person")
    for line in applied:
        print(f"  applied: {line}")
    for line in manual:
        print(f"  by hand: {line}")
    if args.write:
        body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
        RULEBOOK.write_text(_header(text) + body, encoding="utf-8")
        print(f"wrote {RULEBOOK.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
