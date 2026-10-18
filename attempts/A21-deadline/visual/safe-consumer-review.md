# Safe departure integration review

Ready for parent review. Integration patch: `safe-departure-candidate.patch`, relative to the combined candidate, not the original worker baseline. Candidate rules SHA-256: `cf5d6ca4c242170675d3aa75d13f80d937e73b934c584387263078e37eecb714`.

Read the combined `rules.py`, `visual_checks.py` and `events.py`. Confirmed bug: planner-selected `safe_departure` / `safe_open_window(parent_trigger=safe_departure)` records have an actual visible cashier transition but no corresponding log event. The event-only matcher discarded them. Since `apply_checks` skips unknown answers, the safe rule could then retain an unsupported raw CLIP open interval.

Only the safe rule and one regression test change:

- Reuse `safe_attended` to recover the same visible cashier's near-to-away transition at the actual observed timestamp. Local trigger references feed the existing validator; nothing is added to the event log. No room exit is inferred.
- Consume safe check answers only at exact existing sample timestamps. A valid unknown breaks support; no answer is moved to a nearby sample and no time between sparse points is filled.
- Keep existing role/actor, finite time, normalized crop and model/question provenance validation. The parent's complete `verified_checks` method was checked byte-for-byte unchanged, preserving observed-entry/safe-unattended/parent-trigger mappings and `diagnostic_only` rejection.

One focused regression:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_f1_evidence_guards.py::test_safe_departure_unknown_breaks_raw_support_at_its_exact_sample
```

Combined candidate before fix: **1 failed in 0.41s**, because the exact-time unknown left a 4.5-second raw finding. Patched rules: **1 passed in 0.36s**. The same test covers the dense-open control, unknown interruption, off-sample rejection and unchanged event log. Logs: `safe-departure-before.txt`, `safe-departure-after.txt`.

Ruff checks passed with E501 ignored for the two unchanged long lines in the parent matcher; `git diff --check` passed. No full suite, frozen replay, GPU or service run. The fixture is numeric and synthetic; no model-accuracy or legal-validation claim is made. This patch adds no multi-VM production dependency.
