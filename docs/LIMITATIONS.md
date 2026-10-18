# Limitations and known error cases

task.md §8 requires "перечень ограничений решения и известных случаев
ошибок". This page describes the deployed detector, the F1 computer-vision
stack (`DETECTOR=f1`, `docs/ARCHITECTURE_SUMMARY.md`). The earlier version
written for the VLM-first design is in `archive/docs-vlm-era/LIMITATIONS.md`.
Every number below is cited from `attempts/` or marked `TODO(team)` where it
has not been measured yet; nothing here is invented.

## Verdict policy: recall first

The task brief is explicit that a missed violation is worse than a false
alarm (task.md FAQ 16: "ложных срабатываний должно быть как можно меньше,
пропуск нарушения недопустим"). The pipeline is tuned accordingly: a finding
is reported whenever an enabled rule's conditions are met on the observed
timeline, even when its citation is still `pending` (see "Citation
status" below) — the alternative, suppressing a real finding until a human
has verified its law citation, would turn a detection miss into a legal
one. This means **false positives are possible and expected to be more
common than silent misses**; task.md FAQ 15 also warns that invoking
"insufficient data" without justification is itself penalized, so the
service never substitutes an unjustified "no violation" for a genuine
"could not establish this".

## Sampling gap: events shorter than the step can be missed

There is no proposer stage: F1 samples the whole video uniformly at 2 fps
(0.5 s step) and every rule works on that timeline. A state only counts once
it has held for `hysteresis_sec` (0.6 s in `config/perception.yaml`,
`backend/f1/events.py`), which at a 0.5 s step means three consecutive
samples. So **a violation whose visible signature lasts less than about a
second can be missed**. If the 270 s budget runs out before perception finishes,
`coverage.deadline_hit` is `true` and the rules run on what was observed.

## Weak perception

- **Small objects.** On 20 hand-labelled frames, OWLv2, Grounding DINO and a
  VLM each answered only 4 of the 11 cash checks correctly (A13 in
  `attempts/README.md`). Rules that depend on cash, keys, documents or the
  laptop screen inherit that error.
- **Static objects read as new ones.** On X-1 the only finding came from
  OWLv2 matching a fixed object as "a handbag" (A12 trace in
  `attempts/A12-adr002-service-f1/README.md`).
- **False alarms concentrate in a few rules.** On the full 40-video run of the
  same stack (A01), the worst rules were `A-OUTSIDER-ZONE` (71 false events),
  `A-SECOND-PERSON` (31) and `L-NO-DOCS-ON-LEAVE` (13).
- **Door rule never fired correctly.** `A-DOOR-LOCK` scored 0 of 2 on the
  door clips (A01). It needs an observed `ENTER` event and a CLIP "open"
  state 5 s later; missing either means no finding.

## Upload concurrency

The worker runs **one GPU job at a time** (a single FIFO queue); running
jobs in parallel on one L4 GPU does not add throughput, it only splits it
(`archive/research1/architecture.md` §4). A second upload that arrives while a job
is running is queued and starts with less of the 270 s budget already
remaining, so a long video behind another long video can hit the deadline
(`coverage.deadline_hit`); there is no separate, lower-quality code path.
Single-job runtimes for this stack: mean 83.9 s and worst 294.6 s at 5 fps
(A01), 50.8 s cold for X-1 at 2 fps in the deployed service (A12). Two long
uploads at once can therefore exceed the jury's 300 s budget for the second
one; this is a known ceiling of one L4 GPU, not a bug.

## Citation status

Every displayed norm carries a `citation_status`: `"verified"` only if a
human has checked it against adilet.zan.kz and recorded that in
`knowledge/norms.json` (`verified_by`, `verified_at`); `"pending"` means it
still needs review and `"invalid"` means a known citation conflict. The UI
shows each state separately.
**An AI-produced result never marks a citation `verified` on its own**
— the violation is still reported (recall-first policy above), but its legal
grounding is never presented as confirmed until a person has done that check.
As of this writing every norm in `knowledge/norms.json` still has
`citation_status: "pending"`. The screen-lock citation is still an open conflict:
`53-71-9` in the kit vs `48-71-9` in the R1 workbook (see
`knowledge/README.md`). Every citation currently shows as
"ожидает проверки" in the UI. TODO(team): complete the human verification
pass against adilet.zan.kz and record `verified_by`/`verified_at` in
`knowledge/norms.json` before the freeze. Rule-to-clause strength is recorded
per rule because one clause can support different rules with different strength.

## Camera angle

The open dataset and all development runs use one fixed over-the-shoulder
angle (task.md FAQ 3). F1 calibrates zones automatically from the first 2 s
of each video (`backend/f1/calibration.py`): desk, laptop, safe and door
boxes, and cashier/client half-planes around the desk. **The half-plane
split assumes the camera looks over the cashier's shoulder**; a camera that
faces the cashier needs manual zones in `config/overrides.yaml`, keyed by the
video's SHA-256. If calibration is not confident, the result carries a
warning. The jury's final video is filmed from a different angle (task.md
FAQ 4), and the self-filmed clips in `robustness/` are this team's only
other-angle signal before submission:

- TODO(team): fill in from `robustness/README.md`'s results table -
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
  a busy video are not surfaced (`archive/research1/architecture.md` §2).

## Aggregate detection results

Measured on the 40 unique open videos (`attempts/README.md`):

- A01, the same F1 stack at 5 fps before it was ported into this service:
  20/40 correct verdicts, recall 14/21, 13/19 clean videos falsely flagged,
  worst runtime 294.6 s.
- A12, the deployed service: TODO(team) - not scored on all 40 videos yet.
  Record its numbers here once `eval/run_eval.py` has run; never estimate them.
