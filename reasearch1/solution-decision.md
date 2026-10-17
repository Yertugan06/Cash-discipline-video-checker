# ADR-001: Detection approach for the cashier-violation service

> **Superseded in part by ADR-002 (`architecture-decision.md`, 2026-10-17 19:30).** The teammate F1 app's full run failed this ADR's acceptance check (20/40, recall 14/21); the detector is now the VLM state timeline inside the F1 app's service shell.

**Status:** build conditionally, 2026-10-17 ~19:30. Evidence: `problem-validation.md`. There is no previous ADR; the exploration's provisional ranking was F4 > F3 > F1.

## Constraints

- Mandatory:
  - UI plus the two-step API with JSON schema and `X-API-Key`;
  - binary verdict;
  - per event: type, timecode, description, 1–3 JPEG evidence frames, and an RK rule citation;
  - fully local; ≤ 5 min per video; no faces, no audio; commercially licensed models.
- Scoring: 55 of 100 points depend on detection, localization and type. FAQ 16: no missed violations first, then few false positives.
- Deadline: 12:00. Team of 4. Compute: laptop 12 GB plus two Brev L4s; `datathon` is shared with the team's app and a vLLM server.

## What the evidence says

The rival methods are the families F1, F2, F3 and F4 from `problem-validation.md`.

- **No measured method detects better than chance.**
  - Verdicts: 18–23 of 40 correct. The always-violation floor gets 21; the duration shortcut gets 25.
  - Localization: top-1 at best ties the pixel-free prior.
- **The VLM fails at recognition, not search.** Shown the right 8 seconds, Qwen3-VL-4B says "yes" on 8/22 labelled windows vs. 4/19 matched clean twins; Qwen3-VL-8B on 16/22 vs. 15/19. A per-item prompt doesn't help.
- **Generic features carry no signal.**
  - Zone-free COCO rules fire equally on clean clips.
  - DINOv2/SigLIP2 linear probes, leave-one-group-out: video AUC 0.49–0.54.
- **Runtime is not binding:** every measured configuration fits within 5 minutes.

## Decision

1. **Do not adopt F3 (whole-video VLM) or F4 (cascade) as the detector.** Their unique advantage, open-vocabulary recognition, was falsified on these clips at 4B and 8B. The VLM gets no role in the verdict path. Descriptions come from the verified rule catalog's templates, filled with observed events, not from free VLM text. That removes the hallucination risk the brief penalises (§5, criterion 4).
2. **Detection direction: mechanism-specific, object-state perception (F1), not generic F1.**
   - Measure it on the top mechanisms by frequency: 231-20-2 cash on the workplace (8/22), 14-16-1 door (3/22), 231-80 keys and seals (2/22), 48-71-9 unlocked screen (2/22).
   - The teammate's app (`forte-cash-checker`) is the existing implementation of this direction. AGENTS.md says to integrate rather than compete, so **adopt it as the detector, conditional on its full-run metrics** (see the acceptance checks).
3. **Build the mandatory service now**, with the detector behind one interface. The flow is upload → job → verdict → events → evidence frames → citation from the Нормы catalog. It must stay runnable regardless of detector quality.
4. **Verdict policy is an explicit product decision, not a tuned threshold.**
   - With chance-level detection, any threshold trades recall for false alarms one-for-one.
   - Choose the FAQ 16 reading (recall first) consciously and state it in the limitations document.

## Strongest rejected option

**F4 / D, the coverage-first cascade**, was the exploration's first choice.
- It was rejected because both of its stages failed their own tests.
  - The verifier doesn't discriminate (4B or 8B).
  - The proposer adds almost nothing on short clips: motion and uniform windows give the same F4 result.
- It would beat the decision only if a verifier separated labelled windows from matched twins. No tested model did.

## Best feasible hybrid

- The teammate's object-state rules generate candidate events.
- A **crop-level** check could confirm them: a CLIP or VLM yes/no on the desk, door or screen crop at native resolution, not the whole frame.
- Unlike the whole-frame VLM tests, this targets the small decisive cue. **It is untested [H].** Adopt it only if a matched-twin probe on crops beats the rule alone.

## Evidence vs. judgment

- **Evidence:** every number above, reproducible from `validation-evidence/` (scorer verified independently; 4B reproduced across machines).
- **Judgment:**
  - that mechanism-specific perception can succeed where generic perception failed;
  - that the teammate's app is the right vehicle;
  - the verdict policy.

## Opportunity cost and delivery

- Further VLM prompting or larger zero-shot models: low expected value.
- Higher value:
  - the controllable criteria: rule grounding (15), product readiness (10), architecture (10);
  - honest limitations;
  - a measured, frozen configuration of the mechanism-specific detector.
- Training detectors on locally boxed frames for cash/keys: data-limited (about 22 events). Feasible only for one mechanism within 24 h; gated as below.

## Acceptance checks (switching conditions)

| Check | If it passes | If it fails |
|---|---|---|
| Teammate F1, full 40-video run, configuration frozen **before** scoring, no per-video manual overrides, grouped scoring with this harness | Beats always-violation by ≥ 3–4 videos on false alarms at ≥ 19/21 recall, and beats the blind prior on top-1 localization → adopt as core detector | Declare detection experimental. Ship the floor policy plus evidence and citations, and document the limits |
| 145 s clip at the teammate F1 sampling rate on the target GPU | ≤ 300 s end to end → keep 5 fps | Lower the rate, or sample densely only around rule triggers |
| Crop-level matched-twin probe for 231-20-2 (desk crop, labelled vs. twin) | Clear separation → add as confirmer (hybrid) | Drop the hybrid |
| Other-angle re-staged clips (2 phones, matched pairs) | Measured robustness claim | No robustness claim; state "untested on other angles" |

## Fallback

The compliant service with the detector interface, rule-catalog citations, evidence frames and the explicit verdict policy. This keeps the main user flow runnable (AGENTS.md) whatever happens to detection.

## Decision stability

- **Robust to:** more VLM capacity (4B→8B changed nothing) and the prompt format.
- **Would reverse if:**
  - a verifier passes the matched-twin test, which would revive F4;
  - the teammate F1 fails at full scale, which would leave no validated detector.
- **Changes from the exploration's provisional ranking** (F4 > F3 > F1) are driven by **new evidence**, not judgment: C2, C3, A1 and B1 were falsified.
