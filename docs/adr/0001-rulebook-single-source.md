---
status: accepted
---

# The rulebook is the one source for rules and their legal basis

Until 2026-10-18 two rulebooks drove the service: the team workbook (`Cash_Discipline_Cases_Rules.xlsx`, built from the dataset's cases outward) set what F1 detects, and a table inside `scripts/build_knowledge.py` set what the user is shown, and they cited different clauses for the same rule (`L-PC-LOCKED` cited the repealed act 48 on one side and act 53 on the other). We made `knowledge/rulebook.yaml` the one source, written law first (act -> verbatim norm -> requirement -> visible breach -> rule -> violation type), and generate the Knowledge Pack and the `rules` part of `config/f1_codex.yaml` from it, because criterion 4 of task.md §9 penalises unconfirmed legal claims and FAQ 9 says test videos may show violation types the dataset does not.

## Consequences

- F1's own citation fields (`source`, `strength`) are now derived from the rulebook; they were never read at runtime. The workbook's differing citations (e.g. 231 п.75 for `A-OUTSIDER-ZONE`, п.78 for `L-SAFE-LOCKED-ON-LEAVE`, п.31 пп.1 for `C-ID-BEFORE-CASH`, п.25/п.94 for `K-SEAL-CHECK`) were dropped from F1 and go to the human legal review, not into the rulebook.
- A rule may only be enabled for submission when `build_knowledge.py --freeze` passes: every norm it cites is human-verified and its act confirmed in force. Until the review is done the gate is opt-in, because today it would disable every rule.
- `scripts/convert_codex.py` and `config/rule_templates.yaml` are retired; the workbook stays as history and as the source of camera layouts for evaluation.
