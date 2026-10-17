# Limitations and known error cases

task.md §8 requires "перечень ограничений решения и известных случаев
ошибок". This page replaces the earlier (pre-pivot, F1-CV-only) limitations
note with the current VLM-primary architecture (`reasearch1/architecture.md`,
`reasearch1/architecture-decision.md`). Every number below is either cited
from those research documents or marked `TODO(team)` where it has not been
measured yet — nothing here is invented.

## Verdict policy: recall first

The task brief is explicit that a missed violation is worse than a false
alarm (task.md FAQ 16: "ложных срабатываний должно быть как можно меньше,
пропуск нарушения недопустим"). The pipeline is tuned accordingly: a finding
is reported whenever the rules engine's conditions are met on the observed
timeline, even when its citation is still `needs_review` (see "Citation
status" below) — the alternative, suppressing a real finding until a human
has verified its law citation, would turn a detection miss into a legal
one. This means **false positives are possible and expected to be more
common than silent misses**; task.md FAQ 15 also warns that invoking
"insufficient data" without justification is itself penalized, so the
service never substitutes an unjustified "no violation" for a genuine
"could not establish this".

## Sampling gap: events shorter than the step can be missed

There is no proposer stage — the whole video is sampled on a fixed grid,
not pre-filtered to "interesting" moments. Coverage is coarse-first:

- a 4 s grid covers the whole video quickly;
- 2 s "fill" samples are added between coarse points for as long as the
  estimated remaining time allows, under a 270 s per-job deadline.

Measured on saved states (`arch_rule_sweep.txt`, cited in
`reasearch1/architecture.md` §4): the 2 s step gives the same result as 1 s
sampling, while 4 s alone is "offset-sensitive" (lower recall, 6–12/22 any
event within ±3 s vs 13–14/22 at 2 s). **A violation whose visible signature
lasts less than the active sampling step can be missed entirely**, and any
video that hits the deadline before the 2 s fill pass completes is reported
under coarser, offset-sensitive coverage. The UI and the API both surface
this: `coverage.mode` is `"full"`, `"coarse"` or `"partial"`, and the UI
shows an explicit warning whenever it is not `"full"`.

## Weak fields

Two per-frame state fields are measured to be unreliable on the VLM's v1
prompts: `key_in_safe_lock` (0/2 correct on the gold-frame check) and
`desk_cash` (1/3 correct), per `reasearch1/architecture.md` §7. Rules that
depend on these fields (`L-SAFE-LOCKED-ON-LEAVE`, `L-NO-CASH-ON-LEAVE` and
related cash/safe mechanisms) inherit this uncertainty: a missed or
hallucinated small object directly affects whether the corresponding
finding fires. A candidate fix — re-asking the question on a cropped
desk/safe/laptop region at candidate-finding time only — is gated behind a
pre-registered dev-and-lockbox improvement check (`reasearch1/implementation-plan.md`
Phase 4) and is **not adopted unless that check passes**; until then, these
two fields should be treated as lower-confidence than the rest of the state
form.

## Upload concurrency

The worker runs **one GPU job at a time** (a single FIFO queue); running
jobs in parallel on one L4 GPU does not add throughput, it only splits it
(`reasearch1/architecture.md` §4). A second upload that arrives while a job
is running is queued and starts with less of the 270 s budget already
remaining, which produces a coarser sampling plan through the same
deadline-aware mechanism described above — not a separate, lower-quality
code path. Two simultaneous ~145 s uploads are estimated to both still
finish, but three simultaneous long uploads cannot all finish within the
jury's 300 s budget on this hardware; this is a known, documented ceiling,
not a bug (`reasearch1/architecture.md` §4).

## Citation status

Every displayed norm carries a `citation_status`: `"verified"` only if a
human has checked it against adilet.zan.kz and recorded that in
`knowledge/norms.json` (`verified_by`, `verified_at`); otherwise it is
`"needs_review"` and the UI shows the badge "требует проверки" next to it.
**An AI-produced result never marks a citation `verified` on its own**
— the violation is still reported (recall-first policy above), but its legal
grounding is never presented as confirmed until a person has done that check.
As of this writing every norm in `knowledge/norms.json` still has
`human_verified: false`. The screen-lock citation is still an open conflict:
`53-71-9` in the kit vs `48-71-9` in the R1 workbook (see
`knowledge/README.md`). Every citation currently shows as
"требует проверки" in the UI. TODO(team): complete the human verification
pass against adilet.zan.kz and record `verified_by`/`verified_at` in
`knowledge/norms.json` before the freeze (G4 checklist item 4).

## Camera angle

The training dataset and all development/validation runs use one fixed
top-down angle, one camera, one desk (task.md FAQ 3). The VLM's state form
asks semantic questions ("is the cashier at the desk") rather than relying
on calibrated zones, so no per-angle recalibration step exists in the
pipeline — but **no accuracy claim has been measured on a different camera
angle before this document was written**. The jury's final test video is
filmed from a different angle (task.md FAQ 4), and the self-filmed
robustness clips in `robustness/` are this team's only other-angle signal
before submission:

- TODO(team): fill in from `robustness/README.md`'s results table —
  "tested on N self-filmed clips, X/Y", or "untested on other angles" if the
  robustness run did not complete before the freeze.

## Data handling and deletion

Uploaded videos and their sampled frames are deleted when a job ends. The
result JSON (including its embedded evidence JPEGs) is kept for 24 hours
and then purged. Everything — uploads, results, caches — is deleted after
the hackathon window closes, per the organizer's data-use restriction
(task.md FAQ 6: "данные должны использоваться только в рамках хакатона").
No face recognition or identification is performed (task.md FAQ 29); no
audio is used (task.md FAQ 28, videos are silent regardless).

## Other known constraints, by design

- **No closed violation taxonomy.** The organizers do not publish a fixed
  list of violation types (task.md FAQ 8–9), and the test set may contain
  mechanisms outside the training distribution; `docs/VIOLATION_TYPES.md`
  lists only the mechanisms this service actually checks for.
- **Visual evidence only.** The service never claims a violation that would
  require invisible data (ledger entries, system reconciliation) to
  establish, per task.md §7's explicit constraint.
- **Result is a hint, not a verdict.** Every output is meant for human
  review, never presented as a final disciplinary or legal conclusion
  (task.md §7).
- **Ranking is capped.** At most 3 findings are reported per video
  (persistence-ranked, then rule order); additional lower-ranked findings on
  a busy video are not surfaced (`reasearch1/architecture.md` §2).

## Aggregate detection results

TODO(team): once WP1/WP2/WP3 finish the frozen-config run on the full
40-video training set and the jury's own test clips, record the measured
aggregates here (correct/40, recall, false-alarm rate, worst runtime) —
never invent or estimate these numbers in advance of that run (SHARED_BRIEF
rule 5: "no invented results").
