# Owner D3-1: honest event and rule evidence

Own `backend/f1/events.py`, `backend/f1/rules.py`, and NEW tests/test_f1_evidence_guards.py plus
updates to existing rule/event tests only where expectations must change. Do not edit detector,
perception, config, knowledge YAML or replay. D2-2 owns visual verifier; use shared contract.

Add optional trailing Context.visual_checks list[dict] | None default None. Fix generic evidence
errors, not per-file outcomes:
1. C-ID-BEFORE-CASH must not accuse from a detector miss / no ID event. Require actual adequate
   observation evidence of non-presentation, otherwise unknown/no finding. A handful of negative
   frames doesn't prove an interval's absence. X19's applicability remains unverified. Keep actual
   ID_SHOWN events distinct from cash/document and don't borrow another client's presentation.
2. L-NO-DOCS-ON-LEAVE scope says room exit. A brief walk from laptop to safe/equipment is not
   room exit. Check each leave rule's scope instead of globally changing Context.leaves blindly.
3. Review cash-session continuity and stack-merge claims across brief gaps. Current S-NO-MERGE
   only sees new cash accepted while old cash exists; don't claim physical stacking without
   supporting evidence. Preserve conservative observable wording. Improve reassociation only
   where generic tests/evidence justify it; A18/A19 blob context failed.
4. Clip cutoff, no observation and observed failure stay distinct. Never infer future storage
   failure from cash on desk at the last frame.

Run relevant existing tests plus meaningful new tests for complete session, occlusion, cutoff,
out-of-room exit vs equipment movement, correct client ownership and unknown verifier evidence.
Replay existing numeric caches if available, both baseline/new with identical payloads; explain
lost wrong-reason catches honestly instead of preserving them. No GPU needed. First report in30min.
