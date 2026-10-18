# Next experiment: recognition before cash-flow changes

Status: prepared design, not running or measured. The design interview has not yet switched to
implementation. This specifies the next work without changing the detector or deployed service.

## Goal and baseline

Identify cash and ID reliably enough to follow separate client transactions, then report the
correct observable event and time. Start with a small diagnostic before another architecture change.

The integrated cached baseline is **32/40 unique clips, 0/19 clean false alarms, 8/21 misses**.
This measures verdict agreement; several reasons are unsupported. Preserve the source snapshot,
configuration, model revisions and original replay before any experiment. See the
[integration audit](main-integration-and-annotation-audit.md).

## Step 1: compare inputs on the same object observations

Reuse A13's 20 manually selected frames and existing presence labels. Its 11 cash answers and
two ID answers are a small diagnostic, not a representative benchmark. Missing labels remain
unscored. No new second-by-second annotation is required.

The historical cash score of 4/11 is **accuracy, not four detected cash examples**. Re-scoring
the saved answers gives OWLv2 0/7 cash positives found with 0/4 negative false positives;
Grounding DINO 1/7 found with 1/4 false positives; Qwen2.5-VL-7B 0/7 found with 0/4 false positives.
The two ID answers comprise one positive and one negative. See the
[historical confusion counts](../logs/a13-small-object-rescore.json); this was a numeric re-score,
not fresh inference. Report positive recall and negative errors separately in the next comparison.

For a fixed model, prompts and thresholds, compare:

| Condition | Input | Question answered |
|---|---|---|
| A | Current full-frame plus desk-crop processing | What does the present pipeline recover? |
| B | A plus fixed overlapping native-source tiles covering the full frame | Does giving small objects more input pixels help? |
| C | B plus a bounded short sequence around the same observation | Does temporal appearance add useful evidence? |

Freeze tile geometry, sequence length/sampling and aggregation before inference. Use the same
rules across clips. Record the actual processor resize and input dimensions: native source crops
still undergo model preprocessing. Compare inputs within a model before attributing gains to a
different model. A larger locally installed model is a separate conditional comparison, not an
assumed improvement. Rerun A in the same environment; A13's historical scores are not the control.

Important limitation: A13 has frame-presence labels, not human object boxes or track identities.
Score the union of tile outputs against whole-frame labels; do not assign whole-frame truth to
each crop. This is a practical input comparison, not a proven recognition ceiling given perfect
localization. An oracle-crop claim would need independently verified object inclusion. Report
localization uncertainty and the shortage of labeled ID/document/phone hard negatives explicitly.

All conditions answer the same central-frame presence question. C supplies neighboring frames as
context, not extra positive labels: an object appearing only in a neighbor does not change the
central frame's truth. Distinguish insufficient central-frame visibility from absence and do not
count adjacent frames as independent confirmations.

Keep labels, verdicts and filenames out of model prompts. Ask about visible objects and actions,
with an unknown answer. Score invalid responses and abstention coverage explicitly. Report cash
and ID separately, including false positives on available negatives and time per condition.
Use independent negative observations before accepting any broader cash-versus-ID claim.

## Step 2: verify client cash history if recognition improves

Use existing descriptions for this initial development comparison:

| Case | Evidence to recover | Failure to avoid |
|---|---|---|
| X-4 / X-47, one duplicate group | Client 1 leaves; client 2 touches the door at 55 s and is inside closing it at 57 s while old cash remains; ID first, then new cash; new cash is placed on the old pile | Missing-ID explanation; confusing entry with cash stacking |
| X-5 / X-48, one duplicate group | First cash is counted and stored before the next client | Treating all two-client scenes as violations |
| X-38 | Earlier cash remains at the next client session | Losing ownership during brief occlusion |
| X-39 | Cash goes into storage between clients | Assuming a fixed desk side or pile location |
| X-19 | First client provides cash without an observed ID display; organizer label is clean | Treating the provisional blanket ID rule as verified policy |
| X-1 | Visibly handled cash and ID; official positive label near 22 s, cause unresolved | Inventing rejected/counterfeit notes or a manual-counting prohibition |

Keep recognition, association, ownership and rule evidence separate. Short occlusions retain an
uncertain hypothesis; they do not prove storage, abandonment or object identity. Re-confirm after
reappearance. Do not infer cash from counter proximity alone: A18/A19 already failed that approach.
Add tracking changes only if recognition works and measured association failures remain.

For X-4, distinguish the next-entry event around 57 s from the later physical stacking event.
The exact stacking time has not been supplied; X-47's 68 s organizer marker is not an independently
confirmed stacking annotation. Laptop use is the next observed action, not proof of no later count.

## Step 3: integration and acceptance

Before integration, require an observed recognition gain over A on matched inputs with no increase
in errors on the evaluated negatives, and report the small sample's limits. A tie favors the
simpler/faster input. Failure or insufficient labels means report the result and missing evidence,
not retune until the public examples flip.

Any later runtime change must produce supported cash-event reasons, remove X-4's unsupported
missing-ID reason, and preserve clean storage cases. Rerun all 40 unique clips across all setups;
report verdicts, known event timing, explanation discrepancies, abstentions and cold runtime.
Keep zero clean false alarms as the integration target. Report regressions explicitly; never
preserve an unsupported accusation merely to retain 32/40. Timing for unannotated events stays
unscored. A full reason-accuracy percentage cannot be claimed from the current annotations.

Reuse the existing probe/replay formats and one authoritative event/rule implementation. Keep
duplicates and related scenario variants grouped. All open clips have influenced development;
they are not a fresh holdout. Geometry perturbations are stress checks, not proof of performance
on the final unseen camera angle. No filename, clothing, bag-color or fixed-time exceptions.

## Execution constraints and unresolved questions

Use an isolated datathon2 workspace; datathon3 is available for separate work after checking current
ownership. Coordinate with the existing worker pool, assign one owner per changed interface, and
run only one GPU-heavy job per VM. Keep annotation/service data intact. Dataset images and videos
stay on the authorized VMs and never go to cloud AI, including a cloud coding agent's image viewer.
Only numeric/text results return for review. Model inference is local; Opus advice is text-only.

The prior [Opus tracking review](opus-5-5-small-object-review.md) supports testing recognition
before tracking. Its [ID-rule review](opus-5-5-id-rule-review.md) supports separating observations,
labels and policy verification. No new consultation or model measurement is claimed here.

Open items: ID-rule scope/citations, X-1's violation cause, independently verified object boxes and
hard negatives, and the exact later cash-stacking time. These remain explicit unknowns; they do
not require another full annotation pass before the initial input comparison.
