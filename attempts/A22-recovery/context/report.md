# A22 bounded CV context handoff

One public function: `build_llm_context(scene, observations, log, target_t,
window_s=5)`. It consumes the combined candidate's real `Scene`, `Observation`
and `EventLog` types. The window is centered with total width five seconds by
default. It performs no detection, model call, policy check or verdict calculation.

## Deliverables and integration

- `backend/f1/llm_context.py`: finite, JSON-safe facts with a 16,000 UTF-8 byte cap;
  calibrated boxes/scores, geometric actor-role provenance, first/last track
  observations and gaps, exact sampled states/scores/margins, heuristic events,
  explicit missing coverage, cutoff/end reasons, and omission counts.
- `tests/test_llm_context.py`: four small numeric fixture cases.
- `candidate.patch`: complete candidate-relative patch against the supplied A22
  base, including the new module/test and the proposed verifier call site.
- `visual-checks-callsite.patch`: just the shared-file proposal for parent review.
  It was exercised only in `/tmp/a22-llm-context-candidate`; shared base and service
  were not modified. `patch --dry-run` against the supplied base passed.
- `real-context.json`, `real-trace.json`, `smoke-result.json`: actual numeric/text
  artifacts from one pinned cache. No pixels or new inference.
- `run-argv.json`: exact executed CPU argv/environment plus fresh-candidate setup.
  `base-source-pins.json` records the source hashes read from base revision
  `5fae84bc10415111a04b5982d156727ca80f788a`.

The base has no separate `trace.py`; trace construction is `detector.build_trace`.
The worktree's old A21 runtime files were not substituted for the combined base.

## What the local VLM actually receives

The minimal call-site proposal adds a trailing `CheckRequest.context_json` field
and one shared `prompt` property. The full context is retained in diagnostic
evidence; only calibrated object/actor geometry and explicitly selected timing/
coverage fields enter the visible-state prompt. Classifier state predictions,
role expectations, conditional event names, financial sessions and legal/verdict
claims stay outside that prompt. Image evidence stays primary, with unknown for
obscured/unclear content. This reduces answer anchoring; it does not prove that
auxiliary geometry improves a model's answers.

The actual prompt is used consistently by `LocalQwenBackend.ask`, `cache_identity`
and the trace prompt hash. The complete actual context string is also in the
request fingerprint. Context/prompt changes invalidate the old cache identity.
Existing calls without context retain the original question text.

## Evidence semantics / D2-2 interface

No new fixture-use classifier competes with D2-2. No `fixture_evidence` module was
available in the supplied base. Existing event facts named `fixture`, `fixture_id`,
`near`, `near_fixture`, `active_use`, `active_handling`, `evidence_kind` and `source`
are preserved if actually supplied. Unavailable fields are not synthesized.

- An empty detection list or track gap is not observed absence; occlusion versus
  a miss remains unresolved. Sampling cadence is explicitly an estimate.
- `location=hand:*` and `HANDOVER` are identified as existing geometric/transition
  proxies, not proof of possession or physical transfer.
- `session_id` is an observed-in-session association, never verified financial
  ownership. The serializer creates no owner IDs or cash boxes.
- Safe attendance/proximity does not establish active handling or mechanical
  locking. Actor roles remain geometric hypotheses, not verified identities.
- Last cached observation is not asserted to be the true video end. Explicit
  `clip_end`/`observation_gap` boundary events survive event-list truncation.
- Current observation types do not carry per-sample model/weight identities;
  source names identify the actual CV structures and this limitation rather
  than inventing a model provenance or classifier probability.

## Measured CPU check

The explicit cache path/hash is in `smoke-result.json`; it was selected by sorted
cache path for one reproducible numeric smoke, without annotation/label lookup.
The smoke built current events and the actual `build_trace` from 29 observations
(32 events), then serialized target t=5 s. No video/frame decoding was needed.

- Final context: **15,925 bytes**, built in **14.238 ms** in this one run.
- Actual prompt grounding: **1,465 bytes**; classifier states/events excluded.
- Budget omissions: 11 events, one object track, zero actor tracks or selected
  samples. Omissions are explicit, so this is not complete motion evidence.
- Actual prompt/context changes were checked to change the verifier cache
  identity; the fingerprint contains the exact request/prompt used.
- Numeric CV issues visible for upstream review: `person:1` has both `outsider`
  and `cashier` role values in the same trace. Scene confidence is 1.0 while
  counter/safe/door detector scores are 0.152/0.274/0.344. These are coarse model
  hypotheses, not independently established errors or calibrated certainty.
  Cash coverage is false; it cannot become a statement that cash is absent.

Validation actually run against the isolated combined candidate: **4 passed in
0.15 s**. Ruff lint and format passed for new code and the proposed call site;
candidate patch dry-run and `git diff --check` passed. Initial lint issues were
fixed. A smoke assertion caught conditional boundary events leaking through the
window projection; the prompt now uses a positive whitelist and the smoke passes.

No full suite, GPU inference, full40 scoring, deployment or service restart.
All40 public clips influenced development; there is no held-out accuracy claim
and no measured verdict/perception improvement from this serialization slice.
