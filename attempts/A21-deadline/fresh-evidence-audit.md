# Independent findings audit

Organizer files: 42; unique SHA groups: 40; duplicate samples: 2.

Verdict confusion (SHA groups): `{"TP": 10, "FN": 11, "FP": 0, "TN": 19, "missing": 0, "invalid": 0, "failed": 0, "label_conflict": 0}`.

Reason statuses count findings, not organizer reason ground truth: `{"contradicted": 0, "supported": 8, "unknown": 3}`.

Compatible human event timing: `{"with_human_time": 0, "human_time_unknown": 8, "distances_to_human_interval_sec": []}`.

Human observations cover 40 SHA groups; 0 have no supplied event assertions.

Runtime (reported records only): `{"measured_records": 0, "missing_records": 40, "min_sec": null, "median_sec": null, "max_sec": null, "over_300_sec": 0, "provenance": "Supplied wall/runtime fields only; no inference timed by audit."}`.

Invalid records: 0; conflicting SHA groups: 0; unlabelled predictions: 0.

| Files | Binary | Findings and observed reason status |
|---|---|---|
| X-1 | FN | none |
| X-2 | FN | none |
| X-3 | TN | none |
| X-4, X-47 | FN | none |
| X-5, X-48 | TN | none |
| X-8 | TN | none |
| X-10 | TN | none |
| X-11 | FN | none |
| X-12 | TN | none |
| X-13 | FN | none |
| X-14 | TN | none |
| X-15 | TP | L-NO-CASH-ON-LEAVE@15.0: **supported** |
| X-16 | TN | none |
| X-17 | TP | K-SEAL-CHECK@9.5: **supported** |
| X-18 | TP | A-SECOND-PERSON@19.5: **supported** |
| X-19 | TN | none |
| X-20 | FN | none |
| X-21 | TN | none |
| X-22 | FN | none |
| X-23 | TN | none |
| X-24 | TP | L-NO-DOCS-ON-LEAVE@10.5: **unknown** |
| X-25 | TN | none |
| X-26 | TP | L-NO-CASH-ON-LEAVE@12.5: **supported** |
| X-27 | TN | none |
| X-28 | FN | none |
| X-29 | TN | none |
| X-30 | TP | A-OUTSIDER-ZONE@13.0: **unknown** |
| X-31 | TN | none |
| X-32 | FN | none |
| X-33 | FN | none |
| X-34 | TP | C-COUNT-BEFORE-EXIT@15.0: **supported** |
| X-35 | TN | none |
| X-37 | TN | none |
| X-38 | TP | S-CLEAN-DESK-HANDOVER@32.0: **supported** |
| X-39 | TN | none |
| X-40 | TP | W-NO-PERSONAL-ITEMS@19.5: **unknown** |
| X-43 | TN | none |
| X-44 | FN | none |
| X-45 | TN | none |
| X-46 | TP | W-NO-FOOD@12.0: **supported**; W-NO-FOOD@15.5: **supported** |

## Contradicted reasons


## Compatible events and timing

- X-15, L-NO-CASH-ON-LEAVE@15.0: bag_after_exit; human interval unknown; distance unmeasured.
- X-17, K-SEAL-CHECK@9.5: bag_then_immediate_departure; human interval unknown; distance unmeasured.
- X-18, A-SECOND-PERSON@19.5: second_client_during_count; human interval unknown; distance unmeasured.
- X-26, L-NO-CASH-ON-LEAVE@12.5: cash_left_after_exit; human interval unknown; distance unmeasured.
- X-34, C-COUNT-BEFORE-EXIT@15.0: client_leaves_during_loading; human interval unknown; distance unmeasured.
- X-38, S-CLEAN-DESK-HANDOVER@32.0: prior_cash_at_new_client; human interval unknown; distance unmeasured.
- X-46, W-NO-FOOD@12.0: coffee_on_desk; human interval unknown; distance unmeasured.
- X-46, W-NO-FOOD@15.5: coffee_on_desk; human interval unknown; distance unmeasured.

## Duplicate markers and annotation limits

- Human event X-1, id_checked: [6.5, 6.5] s; only a compatible reason can use this timing.
- Human event X-1, cash_received: [8.6, 8.6] s; only a compatible reason can use this timing.
- Human event X-1, counter_loaded: [14.9, 14.9] s; only a compatible reason can use this timing.
- Human event X-1, partial_return: [22, 22] s; only a compatible reason can use this timing.
- X-1: cause unresolved; no reason score.
- X-2: cause unresolved; no reason score.
- Same SHA: X-4 violation [57] s; X-47 violation [68] s. These markers do not identify the reason.
- Human event X-4, X-47, door_contact: [55, 55] s; only a compatible reason can use this timing.
- Human event X-4, X-47, old_cash_at_next_entry: [57, 57] s; only a compatible reason can use this timing.
- Same SHA: X-5 no_violation [] s; X-48 no_violation [] s. These markers do not identify the reason.
- X-5, X-48: recording cutoff; future abandonment unobserved.
- X-10: recording cutoff; future abandonment unobserved.
- X-14: recording cutoff; future abandonment unobserved.
- X-16: recording cutoff; future abandonment unobserved.
- X-18: recording cutoff; future abandonment unobserved.
- X-19: recording cutoff; future abandonment unobserved.
- X-20: recording cutoff; future abandonment unobserved.
- X-21: recording cutoff; future abandonment unobserved.
- X-30: recording cutoff; future abandonment unobserved.
- X-31: recording cutoff; future abandonment unobserved.
- X-32: recording cutoff; future abandonment unobserved.
- X-34: recording cutoff; future abandonment unobserved.
- X-35: recording cutoff; future abandonment unobserved.
- X-37: recording cutoff; future abandonment unobserved.
- X-38: recording cutoff; future abandonment unobserved.
- X-39: recording cutoff; future abandonment unobserved.
- X-40: recording cutoff; future abandonment unobserved.
- X-43: recording cutoff; future abandonment unobserved.
- X-44: recording cutoff; future abandonment unobserved.
- X-45: recording cutoff; future abandonment unobserved.
- X-46: recording cutoff; future abandonment unobserved.

## Prioritized source-review assumptions

- P0 physical-id-first-policy: Verify transactions requiring physical ID before cash, permitted alternatives, and adequate evidence of non-presentation. Clean X19 is an applicability counterexample to investigate, not proof that ID is universally unnecessary.
- P0 room-exit-versus-workstation-away: Review whether each clause requires leaving the room or leaving the workstation. Walking to the safe/equipment cannot itself prove room exit; X20's document-exit finding has the wrong observed trigger.
- P0 cash-handover-versus-physical-combination: Keep prior-session cash present at next entry separate from actual combination. New cash received beside old cash does not prove stacking/mixing, and presence-only model answers cannot establish cash owners or boxes. X4/X47 support both events, with combination time unknown.
- P0 cutoff-and-negative-visibility: Require a visible trigger and adequate observation interval; unknown/model failure is not absence. X43/X45 end during or after processing, so do not infer future abandonment.
- P1 x1-unresolved-cause: Identify the actual prohibited act in X1 before evaluating a reason. The counter accepts the notes and some notes are hand-counted/returned; counterfeit, rejected-note, off-camera-check, and manual-count prohibition claims are unsupported.
- P1 key-and-rejected-note-procedure: Review key-left-after-exit and rejected-note recombination procedures separately. A rule about returning a rejected note to a client is not equivalent to recombining rejected notes without detector inspection; better perception alone does not implement either procedure.
- P1 state-versus-legal-conclusion: Verify unattended thresholds and what closed/open/locked states actually establish. Visible closure alone cannot prove mechanical locking; a detector-supported state is not a verified legal citation.

## Capability gaps

- X22-key-after-exit: Human account describes a key left after cashier exit. knowledge/rules.yaml disables L-SAFE-LOCKED-ON-LEAVE and backend/f1/rules.py has no evaluator for it. Perception changes alone cannot enable this rule.
- X44-rejected-notes-recombined-without-check: Human account describes rejected notes recombined without detector inspection. Both candidate rules are disabled/unimplemented; their existing descriptions (whole-video manual counting/no detector, or returning notes to a client) do not directly implement that procedure.

## Limits and provenance

Assertions: `A21-human-text-review-all40-2026-10-18`.

- Partial observations are transcribed from the assignment; this worker has not inspected organizer images/videos.
- No cross-file cash history, appearance/position shortcuts, or timestamp adjustments are evaluation evidence.
- An absent ID recognition or a few negative stills cannot establish non-presentation; adequate interval visibility is required.
- Recording cutoff cannot establish future cash abandonment.
- All legal/policy applicability remains pending source review under RULE_SCOPE=detector.
- All 40 groups were text-reviewed; this is not complete timed event annotation coverage. Only X1 manual rows and X4 explicit clarifications supply human event times.
- Clean binary labels never prove all actions compliant. Missing prose never proves absence; uncertain/occluded states stay unknown.
- X2/X3 descriptions retain their ai_draft origin despite done status. Model suggestions and automatic review timestamps are not promoted into independent human event times.
- X11/X12 screen state remains unknown; X35 hypothetical counterfeit and occluded detector contact are not facts.
- A supported quick-visit proxy in X17 is not direct seal inspection evidence; X15 bag contents and X40 exact desk placement remain qualified.
- Organizer verdicts/timestamps do not establish the reason or its legal validity.
- No overall reason accuracy: human coverage is partial and causes can be unknown.
- Per-file offsets never give timing credit to incompatible/unknown reasons.
- API images, full API schema, and legal citations are not validated by this audit.

Exact input paths and hashes are in the JSON report's `inputs` field.
