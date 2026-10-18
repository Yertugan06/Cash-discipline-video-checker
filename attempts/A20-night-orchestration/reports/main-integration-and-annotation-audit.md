# Main integration and annotation audit

2026-10-18. Incoming main: `7bc47e7` (46 commits after `0ab0258`). The local annotation,
description-drafting and saved-run features were reapplied; three overlapping files were resolved.
The integration remains uncommitted. The design interview is in progress; this report makes no
new detector or model changes.

## What the combined work provides

| Area | Change | Verified outcome / limit |
|---|---|---|
| F1 event/rule logic | Observed-entry handling, client-session tracking, persistent leave evidence, equipment/worn-clothing filtering, quick collection visits, scene-relative distances and ranking | Merged replay agrees with main's recorded API run on every verdict and rule ID across 40 unique clips. |
| Rule source | `knowledge/rulebook.yaml` generates rule/norm outputs; lifecycle, implementation and citation status are separate | 21 registered rules, 15 enabled, 20 pending citations, zero jury-eligible rules. Current evaluation uses `RULE_SCOPE=detector`; legal verification remains pending. |
| Evaluation | Cached replay, timing, geometric/drop probes, API driver and output validator | Main records a full API run; this integration reran cached rules, scoring and timing. Fresh GPU inference was not rerun. |
| Realtime and annotations | Existing live/compare/upload features plus saved-run browsing, description editing, local drafts, feedback and versioned saves | 42 reviewed records preserved; description-only records are excluded from timed event scoring. Upstream realtime files were unchanged over the fetched range. |
| Optional desk history | Preserved the pre-existing experimental switch, disabled by default | Main's enabled-rule filtering remains intact. Its test fixture now supplies the calibrated safe/open state required by the existing strict-origin logic. |

The full Python suite passed: **761 passed, 7 skipped**. The skips cover external deployed
acceptance, unavailable full local dataset, and real GPU inference. Realtime JavaScript: **30
passed**. React frontend: **4 test files passed**, TypeScript and production build passed. Ruff
passed for backend, realtime, tests, scripts and eval. See [validation](../logs/main-integration-validation.txt).

## Comparable results

All rows use the same 40 unique open videos (19 clean, 21 positive). Duplicate files count once.

| Version | Correct | Clean false alarms | Missed positive clips | Meaning |
|---|---:|---:|---:|---|
| Earlier datathon2 preview / A17 | 25/40 | 5 | 10 | Recomputed from the preserved preview snapshot; its file-level total was 26/42. |
| **Integrated A20 cached replay** | **32/40** | **0** | **8** | Actually rerun after the local merge. Same verdicts and rule IDs as main's recorded API run. |
| Teammate VLM v3 | 32/40 | 1 | 7 | Re-scored existing recorded outputs; no rerun or integration of that prototype here. |
| Door/screen combination | 34/40 | 0 | 6 | Union of saved outputs; a paper combination, not an implemented runtime result. |
| Door/screen/collector combination | 35/40 | 1 | 4 | Same paper-combination limitation. |

Integration evidence: [replay](../logs/main-integration-replay.jsonl),
[score](../logs/main-integration-score.txt), [timing](../logs/main-integration-timing.txt).
For the 13 caught positive clips, mean absolute anchor offset is 1.538 s; 11/13 are within 3 s.
This timing score does not establish that each finding describes the correct behavior.

## Annotation interpretation established during the interview

- The user confirms **one fixed camera position and angle**, with several room/table/equipment
  setups and groups of scenarios under those setups. These are not different camera viewpoints.
- References to the previous video may supply setup context. They do not establish cash/client
  continuity between files. Cross-file transaction continuity remains unspecified.
- The user clarifies that X-43/X-45 end after counting. Their continuation cannot be inferred:
  cash visible on the desk at the cut-off does not establish later abandonment or a later client.
- Keep setup geometry and transaction progress as separate concepts. Initial cash ownership,
  events before the clip, occluded actions and events after the cut-off may be unknown.
- An action omitted from a prose description is not automatically an observed absence.
  X-2's text, for example, does not explicitly say that no ID was shown.
- X-11/X-12 have identical supplied descriptions; the text cannot resolve the screen-lock
  difference suggested by their different organizer labels.
- X-1 clarification: the user reports that the counter accepted all notes as valid, followed by
  manual counting and return of some cash around the organizer's 22-second marker. The indexed
  organizer label remains positive at 22 s. The team workbook's earlier rejected-note explanation
  was explicitly tentative/low confidence, and generated ground truth marks its human explanation
  unreliable. The reason is unresolved; do not label this as a rejected/doubtful-note return.
- The user further confirms X-1's hand count and notes are clearly visible to a human observer.
  Out-of-view counting is not an established explanation either. The user's new proposal is to
  infer small-object identity using motion/tracking; this requires a new evidence test, not a
  hand-counting violation rule.
- Answering the paused-frame question, the user confirms that humans can distinguish the ID
  document and money with certainty. The existing crop-first diagnostic is therefore supported,
  while model recognition performance and sampled-frame coverage remain unmeasured.
- **Correction to the earlier ID-first claim:** the user confirms that in X-19 the first client
  hands over cash without first showing ID; the second client shows ID. They retract their earlier
  assertion of a blanket ID-first requirement. The organizer label remains clean. This challenges
  the general visual rule's validity/scope; it does not establish that identification is never
  required or that every visible action in a clean-labeled clip is legally compliant.
- `C-ID-BEFORE-CASH` remains enabled and business-confirmed in the current YAML, with pending
  citations. Treat its policy scope as provisional/unverified pending source and observability
  review. No runtime change, label change or X-19 exception was made during the design interview.
  Preserve object identity independently of expected order and distinguish a missed ID detection
  from an observed absence of presentation; another client's ID cannot satisfy the first session.
- X-4's 57 s clarification: the first client has left and his cash remains on the table; the
  user considers the preceding service correct and describes movement/brief visibility of the cash.
  Previously accepted cash left outside storage is the leading explanation. Paragraph 20's second
  paragraph requires previously accepted cash to be kept in lockable cash-storage equipment;
  see the [indexed official text](https://old.adilet.zan.kz/kaz/docs/V1900019680/compare/rus).
  The user subsequently confirms that client 2 touches the door at 55 s and is inside closing it
  at 57 s. Together with the previous cash still on the desk, this supports the existing
  `S-CLEAN-DESK-HANDOVER` mechanism around 57 s. It is a supported explanation consistent with the
  label, not independently confirmed organizer intent. Door contact alone does not establish
  entry, and movement/temporary occlusion alone does not establish a breach. Keep later cash
  mixing separate; canonical citation statuses and runtime rules remain unchanged.
- The user additionally confirms that client 2's cash is placed directly on top of client 1's
  remaining pile, then the cashier turns to the laptop. This supports a separate `S-NO-MERGE`
  observation, anchored to physical combination; no exact stacking time is supplied. Laptop use
  is the next action, not by itself another violation or proof of no later counting. The latest
  wording initially said "ID after money", but the user explicitly resolved the ambiguity as
  **ID first, then money**, consistent with the original description. The current missing-prior-ID
  explanation is therefore contradicted by the clarified observations. The general ID rule's
  applicability remains unverified; that separate policy question is not settled by this clip.

## Current findings compared with the supplied observations

This is a **text-to-result audit**, not an independent rewatch or legal finding. “Consistent”
means the description supports the reported behavior; it does not prove the event time, a hidden
object, or the norm's applicability. “None” is the model's `no_violation` output for this clip.
The latest integrated replay is used; the datathon2 service remains the earlier deployment.

| Clip(s) | Organizer | Current F1 finding | Comparison with annotation |
|---|---|---|---|
| X-1 | violation | None | User reports all notes accepted, followed by clearly visible hand counting/partial return near 22 s. Organizer-positive with cause unresolved; rejected-note and out-of-view explanations are unsupported. |
| X-2 | violation | None | Cash is accepted and loaded into the counter. ID handling is not described; omission alone cannot establish absence. |
| X-3 | clean | None | Consistent with the reviewed description: ID examined, cash received, counting starts with client present. |
| X-4 / X-47 | violation | `C-ID-BEFORE-CASH` @66 s | **Reason contradicted by clarified observations:** client 2 shows ID first, then gives cash, consistent with the original notes. Entry at about 57 s with previous cash still on desk supports `S-CLEAN-DESK-HANDOVER`; later putting client 2's cash on that pile supports `S-NO-MERGE` (exact stacking time unspecified). X-47 is the identical file with a 68 s organizer marker; the two cash events remain distinct. |
| X-5 / X-48 | clean | None | Cash counted and put in the safe before the next client. Key presence during service is distinct from a key remaining after cashier departure; cash is partly occluded. |
| X-8 | clean | None | Counted cash goes into the safe; records are made in a notebook. Lack of laptop entry alone does not establish a missing record. |
| X-10 | clean | None | Phone is put away; counting starts; clip ends. Initial desk-cash ownership is not established by this clip. |
| X-11 | violation | None | Verdict miss by organizer label, but identical X-11/X-12 text does not establish the screen state. Needs a focused check. |
| X-12 | clean | None | No contrary behavior established by the text; screen locking remains unspecified. |
| X-13 | violation | None | **Missed described sequence:** bag opened, three cash bundles taken directly to safe without an observed recount. This evaluator exists; relevant perception/sequence evidence is missing. |
| X-14 | clean | None | All three bundles recounted before storage. Temporary desk placement occurs during the visible operation. |
| X-15 | violation | `L-NO-CASH-ON-LEAVE` @15 s | Supports bag-left-on-desk after cashier exit. “Cash bag” is contextual; contents are not shown in this description. |
| X-16 | clean | None | ID checked, bag accepted, visitor stays. Recording ends before subsequent inspection/recount can be assessed. |
| X-17 | violation | `K-SEAL-CHECK` @9.5 s | Supports immediate departure after bag handover. The implementation uses visit behavior as a proxy, not direct observation of the seal. |
| X-18 | violation | `A-SECOND-PERSON` @19.5 s | Supported: second visitor hands over ID while first client's counting is active. |
| X-19 | clean | None | User confirms first client hands over cash without showing ID; second client shows ID. Cash is counted/stored before the next client. Counterexample to the assumed blanket visual ID-first requirement; policy applicability remains unresolved. |
| X-20 | violation | `L-NO-DOCS-ON-LEAVE` @1 s | **Reported reason unsupported:** annotation describes an open safe followed by counting, without a room exit. Check event/absence semantics and the safe-state signal. |
| X-21 | clean | None | Safe is closed/locked before returning to count cash; consistent with the described contrast to X-20. |
| X-22 | violation | None | **Capability gap:** key remains after cashier exit. `L-SAFE-LOCKED-ON-LEAVE` is unimplemented/disabled. Better perception alone would not enable it. |
| X-23 | clean | None | Laptop locked, safe locked, key taken before exit; consistent with description. |
| X-24 | violation | `L-NO-DOCS-ON-LEAVE` @8 s | Notebook/jars remain according to context. Whether this notebook meets the document category needs confirmation. |
| X-25 | clean | None | Notebook and jars put in safe before departure; consistent. |
| X-26 | violation | `L-NO-CASH-ON-LEAVE` @12.5 s | Supported: cash stays on desk while cashier takes key and leaves. |
| X-27 | clean | None | Cash put in safe, safe locked, key taken before departure; consistent. |
| X-28 | violation | `L-PC-LOCKED` @8 s | Supported by the author's explicit statement that laptop is left unblocked during departure. |
| X-29 | clean | None | Laptop locked and key taken before exit; consistent. |
| X-30 | violation | `A-OUTSIDER-ZONE` @13 s | Open door and visitor at doorway are described. Crossing into the cashier work zone is not established by that wording. |
| X-31 | clean | None | Door closed before equipment start; consistent. |
| X-32 | violation | None | **Missed described state:** door left open while equipment is started. Door-state perception/temporal coverage needs checking. |
| X-33 | violation | None | **Missed described state:** open door and observer leaning into its aperture. Entry into the cashier work zone still needs separate evidence. |
| X-34 | violation | `C-COUNT-BEFORE-EXIT` @15 s | Supported: client leaves as cash is loaded, before observed count completion. |
| X-35 | clean | None | Detector use is inferred from leaning/pause; actual bill-to-detector contact is occluded. Keep the author's uncertainty. |
| X-37 | clean | None | Counting begins with client present; clip ends. No later departure or storage outcome established. |
| X-38 | violation | `S-CLEAN-DESK-HANDOVER` @32 s | Supported: first client's cash stays on desk when second client starts service. |
| X-39 | clean | None | Cash goes into safe between clients. Key visibility is occluded; preserve uncertainty. |
| X-40 | violation | `W-NO-PERSONAL-ITEMS` @19.5 s | Personal coat/bag are left at the workstation. Exact desk placement/region needs visual confirmation. |
| X-43 | clean | None | Consistent with visible portion: rejected notes checked, cash placed on desk, recording stops. Later custody is unknown. |
| X-44 | violation | None | **Capability gap:** rejected notes recombined without described detector check. `C-DETECTOR-CHECK` is unimplemented/disabled. Rejection is not proof of counterfeit. |
| X-45 | clean | None | Rejected notes individually checked, manually counted and stamped; recording stops. Later custody is unknown. |
| X-46 | violation | `W-NO-FOOD` @12 /15.5 s | Coffee drinking/desk placement is described. Check whether the two findings represent one continuous episode. |

**32/40 is verdict agreement, not 32 verified explanations.** X-4/X-47's supported cash events
and contradicted ID reason, plus X-20's unsupported reason, show why label agreement,
event accuracy and reason/type accuracy must be tracked separately. There is insufficient
independent event ground truth to report a complete reason-accuracy percentage.

## General mechanisms to test after the interview

These are design constraints and hypotheses, not implemented changes:

1. Separate scene geometry from cash/visitor workflow. Infer geometry from the input; do not
   select policy by file ID, clothing, green bag color, or a known desk position.
2. Track an observed cash batch through hand, desk, counter and safe, with operation/owner and
   unknown states. Use visible transitions rather than inferring complete transactions.
3. Preserve the distinction between no observation, occlusion, clip cut-off and observed failure.
   Keep “safe door closed,” “locking motion,” and “key present” as different facts.
4. A cashier stepping to equipment/safe and a cashier leaving the room are distinct events.
   The current shared leave evaluator should be checked against each rule's documented scope.
5. Keep duplicates and paired variants together in evaluation groups. Use setup/scenario groups
   for stress checks; this one-camera dataset cannot establish performance on unseen cameras.
6. Evaluate wrong reasons inside positive clips as errors. A union of plausible findings is not
   enough; require correct visible evidence, reason, timing, runtime and clean-clip behavior.
7. Recheck `C-ID-BEFORE-CASH` source, applicability and observability in light of the clarified
   X-19 sequence. Do not convert this into an X-19 exception or remove the rule solely to improve
   the public-label score. X-4/X-47's ID/cash order is now explicitly clarified as ID first;
   its current missing-prior-ID reason remains contradicted by the human observations.

No application implementation is being changed during the `grill-me` interview. X-1's visibility
question is answered: clearly visible to the human observer. Its cause remains unresolved. A
read-only Claude Opus 5.5 high-effort review of the tracking proposal completed with the user's
explicit approval for selected code, annotation text and results; see the
[review and verification notes](opus-5-5-small-object-review.md). The paused-frame question is now
answered: the user can distinguish ID from money in a still, supporting the crop-first diagnostic.
X-19's first-client non-presentation is clarified; ID-policy applicability, desk-policy details and
cross-file continuity remain open. Unobserved events after X-43/X-45 end must not be assumed.
A follow-up Opus text consultation on the rule-evidence issue completed after the user explicitly
approved the new prepared packet. The verified model was `claude-opus-5-5`, invoked at high effort;
see the [response and checked qualifications](opus-5-5-id-rule-review.md). Its advice adds no
performance result or legal verification. No approval blocker remains for this consultation.
