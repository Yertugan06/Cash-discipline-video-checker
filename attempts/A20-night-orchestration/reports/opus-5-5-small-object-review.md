# Claude Opus 5.5 review: small objects and tracking

## Consultation record

- Requested by the user; explicit approval covered selected code, annotation excerpts and measured
  results. The first detailed submission was blocked pending this approval; it ran after approval.
- Verified response model: **`claude-opus-5-5`**. CLI flag: **`--effort high`**.
- Claude Code 2.1.302; separate print-only session, safe mode, all tools and MCP access disabled,
  no session persistence. Supplied material was text/code/metrics; no dataset video, frame or credential.
- Project-specific consultation completed in 72.6 s. This is review latency, not detector runtime.
- Original input, response and request metadata are preserved under
  `runtime/consultations/datathon26-opus55-review-20261018T021014Z/` (gitignored).
- The [official model/effort reference](https://platform.claude.com/docs/en/models/opus-5-5/migration-guide)
  was checked before invocation. The returned `modelUsage` independently confirmed the model.

## Provisional decision after review

The useful first experiment is an **identity-given-localization diagnostic**: compare the current
input with a native-resolution object crop, then with a short native-frame sequence. A larger
local model is a candidate in that comparison; its improvement has not been measured. Add more
tracking machinery only after establishing whether the pixels/sequence can identify the object.

This is distinct from A18/A19's context-based naming of desk blobs. Current tracking is per label,
so it cannot create reliable cash evidence for an item that never receives a cash/bundle label.
Class-agnostic proposals and soft identity hypotheses remain a possible next step, conditional on
measured localization, recognition and association results.

Adopted design constraints:

- Separate localization, association, identity, action and rule evidence, including their uncertainty.
- Do not count repeated blurry frames or correlated counter/zone cues as independent confirmation.
- Preserve unknown states through occlusions/cut-offs; validate identity again after reappearance.
- Keep duplicates and paired scenarios together, report public-set development results honestly,
  and require independent recordings before claiming unseen-camera generalization.
- Score object/event/reason accuracy separately from binary organizer-label agreement. X-1's
  accepted, visibly hand-counted returned cash still has an unresolved violation cause.
- Start with a small diagnostic and use the existing descriptions. The reviewer's suggested larger
  annotation exercise and numerical bars are proposals, not new requirements or validated thresholds.

No detector implementation or new inference experiment was performed during the interview.
The paused-frame question is now answered: the user confirms that humans can distinguish the ID
document and money with certainty. This supports the proposed native-resolution crop diagnostic;
it does not establish recognition performance at the model's sampled resolution. Tracking remains
conditional on measured recognition and association failures.

The user subsequently retracts their earlier blanket ID-first claim: in clean-labeled X-19 the
first client hands over cash without first showing ID; the second client shows ID. The observation
is now clarified, while policy applicability remains unresolved. Preserve that distinction rather
than treating ID presentation as universally mandatory or universally unnecessary. Expected order
must not determine object identity, and a missed detection is different from observed non-presentation.

This clarification postdates the original successful Opus review below. A separate follow-up
consultation initially required specific approval for the new text packet. The user then approved
it explicitly, and the invocation succeeded with verified `claude-opus-5-5` and `--effort high`.
See the [ID-rule evidence review](opus-5-5-id-rule-review.md) for the response and checked
qualifications. No runtime rule flag has been changed.

## Verification notes: advice is not automatically a code fact

1. **Tracker buffer claim corrected.** The original review below says the buffer is about 15 s.
   The installed Supervision 0.27.0 constructor on datathon2 instead computes
   `max_time_lost = int(frame_rate / 30.0 * lost_track_buffer)`. At the configured 2 fps and
   buffer 30, that is **2 updates**, nominally about one second; removal uses a strict comparison.
   See the [versioned primary source](https://github.com/roboflow/supervision/blob/0.27.0/supervision/tracker/byte_tracker/core.py).
   Do not change tracking parameters based on the review's 15-second interpretation.
2. **Fragmentation needs qualification.** `MoneyFlow.record` already reassociates cash/bundle
   detections across some short gaps using position/time. Per-label association can still lose
   continuity, but every temporary label change does not necessarily mint a new cash identity.
3. **Abundant blobs do not prove good localization.** A18's many candidates are not measured recall
   of real cash instances. The diagnostic must assess whether the real object is in the candidate
   region rather than assuming localization is solved.
4. **Motion can support a hypothesis.** The review's appearance-only confirmation policy is a
   conservative proposal, not a general theorem. A validated discriminative action may contribute
   evidence; mere proximity to a counter cannot establish object identity or a physical transfer.
5. **Numerical acceptance bars remain unregistered.** The suggested 80%/60% episode thresholds and
   crop budget are expert suggestions. They are not observed performance or a proven operating point.
6. **A13's 4/11 cash score is accuracy, not cash-positive recall.** Re-scoring existing saved
   answers finds 0/7 cash positives for OWLv2, 1/7 for Grounding DINO and 0/7 for the 7B VLM;
   their false positives on four cash-negative frames are 0, 1 and 0 respectively. The original
   review's "cash in 4/11 instances" wording is misleading. See the
   [numeric re-score](../logs/a13-small-object-rescore.json). No model was rerun for this check.

## Original project-specific review (verbatim; corrections above apply)

# Review: class-agnostic tracks plus temporal crop identity

## 1. Verdict and weakest assumptions

The proposal is reasonable as an eventual architecture, but it is premature as the next experiment. It bundles five problems with very different evidence behind them:

- **Localization.** This is probably not the bottleneck. A18 found objects; blobs were plentiful. The cost of more localization is false candidates (body and desk edges, reflections), not missed ones.
- **Association.** The current code fragments identity structurally:
  - Per-label ByteTrack means a cash/paper label flicker starts a new track, and MoneyFlow mints a new `cash-N`.
  - `minimum_consecutive_frames=1` admits one-frame tracks.
  - `lost_track_buffer=30` at 2 fps is about 15 s of coasting.
  - Class-agnostic tracks would fix the plumbing, but plumbing was never the measured failure.
- **Semantic identity.** This is the demonstrated weak link. A13 found cash in 4/11 instances across three model families. A18 had only 14/191 objects overlapping a detector label. Nothing in the proposal yet shows that pixels at the system's input carry identity.
- **Action inference.** Fanning and card inspection are genuinely new cues. They are also brief gestures, and 2 fps sampling of resized frames may alias them away.
- **Business-rule evidence.** Even perfect identity and motion do not establish a violation. X1's cause is unknown, X43/X45 end before any outcome, and "rejected" does not mean counterfeit.

**Weakest assumption:** "a human sees it clearly" implies "the pipeline's input contains it." The human watches native resolution, native frame rate and continuous motion. The pipeline sees 2 fps frames, resized for the detector, and object passes only every `object_interval_sec`. Until that gap is measured, a bigger model or tracker is a guess.

**Second weakest:** "visible counter transfer" and similar interaction cues are A18's origin clue renamed. Any cue derived from where the hand came from or what equipment was active is correlated with the event and cannot independently confirm identity.

## 2. Smallest first experiment

Run an **identity-given-localization ceiling probe**. It needs no tracking and no rules.

Using human-boxed object episodes (section 3), score identical instances under these conditions:

- **A. Current input:** the full frame as the detector receives it (resized), with the current OWLv2/OpenCLIP prompts. This is the baseline.
- **B. Native single crop:** a native-resolution crop around the human box, plus a context margin, scored with the same models.
- **C. Native short sequence:** about 8–16 native-fps frames around the episode's clearest moment, with frame scores aggregated. This tests whether temporal appearance helps beyond B.
- **D. Candidate larger local model:** B and C with a larger offline model that fits on the L4 next to the pipeline. This is a candidate requiring measurement. A13 already showed that bigger is not automatically better.
- **Negatives:** matched native crops of documents, receipts, ID cards, phones, empty hands, desk edges and reflections. These must come from both clean and positive clips.
- **Context-prior-only control:** A18-style origin/counter clues alone, with no pixels. Any later fused system must beat this control and must not just reproduce it.

Before any of this, take a free measurement: a histogram of the native pixel size of the annotated cash. If bundles or notes are only a few dozen pixels on their long side, stop and say so.

**How this differs from A18/A19:** they asked whether context can name a blob. This asks whether the pixels can name a correctly localized object, at what resolution and frame rate. If B and C fail, the whole candidate design fails cheaply. If B passes and A fails, the fix may simply be targeted native crops on hands and safe, not a new architecture.

Run cross-validation over **setup/scenario groups**, never over clips, so that table appearance does not leak.

## 3. Minimal ground truth for a tired annotator

Use the existing annotation UI on roughly 14–16 clips, not all 42:

- the 8 misses;
- X4/X47 (one copy only);
- about 6 clean clips with similar cash handling, preferring those that produced A18/A19 false alarms.

**Per object episode** (cash bundle, loose notes, ID/card, document, other, unclear):

- one box on the clearest frame;
- first and last clearly visible time (±1 s);
- each location change (hand, desk, counter, tray, safe, client), with an approximate time and a **mandatory seen / occluded / inferred flag**. This is what preserves X35 and X48 honestly.

**Point events:** counter start/end, detector check, safe open/close, key left in lock, leaving the workstation versus leaving the room, and clip ends mid-operation.

**Hard negatives:** one box each for 1–2 look-alikes per clip.

**Agreement check:** re-annotate about 4 clips later, or with a second person. The annotator is not blind to the organizer labels; record that limitation rather than hide it.

## 4. Pre-registered bars

Freeze these before running anything.

**Stage 1: identity**
- Proceed only if condition B or C confirms at least 80% of visible cash episodes (at least one confirmed crop per episode), with at most 1 hard-negative episode named cash per 10.
- The gain over A must exceed the observed annotation disagreement.
- If B and C both fall below 60% recall, stop. The limit is pixels or occlusion, not the method.

**Stage 2: tracking, only if stage 1 passes**
- An identity carried across occlusion counts only when it is re-confirmed by appearance on the same track.
- Wrong carry-over (identity attached to a different object) must be 0 in clean clips.
- Unconfirmed carries must emit `unknown`. Report the rate of re-confirmation.

**System level**
- Clean false alarms stay at 0/19. Any new clean false alarm fails the change.
- A positive counts as reason-correct only if all three hold:
  - the rule ID matches the annotated event;
  - the evidence time is within ±2 s;
  - the evidence object type matches.
- No regression on currently reason-correct positives.
- X4/X47 must stop citing C-ID-BEFORE-CASH, or that output is counted as a reason error.

**Special clips**
- X1, X11 and X12 are scored verdict-only, with their original labels preserved.
- Any X1 explanation asserting counterfeit, rejection, off-camera counting or a manual-counting prohibition is a reason error.
- X43/X45 must not produce an abandonment inference.

**Latency:** the longest clip must complete within 270 s on the L4, offline, with a stated extra budget for crops (for example ≤ 60 s). Report the median and the worst case across 3 runs.

**Validation**
- Report every per-clip change across all 40 clips.
- Label all public-set results as development results, because every clip has already been seen.
- Freeze the code hash and thresholds before evaluating any new recordings or a hidden set.
- New-camera generalization remains unclaimed.

## 5. Pointed question and failure mode

**Question for the user:**
> "On the misses, if you pause on a single frame, roughly where the pipeline samples, can you still tell cash from a document or ID card? Or do you only know it's cash because you watched it move?"

The answer decides between resolution/crop work (still frames are legible) and motion-based identity (only motion is legible). It also tells you whether the human certainty is itself partly inferred.

**Most likely confident false accusation:** circular reinforcement. A document or ID in hand near the counter is softly called cash because of the interaction context. The hypothesis then coasts through a body occlusion and lands on the desk, and an abandonment or not-in-safe rule fires on a clean clip.

Every step looks locally plausible; none was appearance-confirmed. Three safeguards:

- Context cues may lower uncertainty about *where* to look, but never upgrade identity.
- Only appearance on the same track can confirm identity.
- Rules must refuse to fire on inferred or occluded legs without a confirmed endpoint.

## 6. Capability claims

- Native-resolution crop benefit, temporal aggregation and the larger local model's identity accuracy are all **candidates requiring measurement** on this footage.
- No benchmark gains are asserted.
- Nothing above implies a legal cause for any clip.
