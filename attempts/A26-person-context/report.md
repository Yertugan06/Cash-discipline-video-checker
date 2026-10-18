# A26: location-derived outsider identity after cashier track loss

Candidate only; not applied. Declared base shared/a23/base main4a3b9ea. First diagnosis under1minute; first full CPU result at05:31UTC. No model/GPU/video/annotation/service/cache mutation or new video evaluation. Source SHA pins are in source-pins.json; each40 cache input and8 mirrored traces is pinned in results.json.

## Numerical root cause

Exact mirroredX11 trace is `4b9b88383d4f47089971fa6aef292a2b.json`, SHA `a3b67344d3235a68d1e1efa3e0e0755f9107a7f7f95beb1995872babd07b85e8`, matching publication metadata.

- person:1 is observed0–20.0s and is cashier from1.0s. No in-room person is observed20.5s. Its EXIT is emitted at20.5s.
- person:19 first appears21.0s, alone through23.5s (6samples). The first five samples are outsider, then it becomes cashier at23.5s. There are **zero samples in which person:19 and a separately visible cashier coexist**.
- Its person scores21–23.5s are .803/.801/.848/.828/.880/.875 in the rounded numeric trace. High person scores cannot establish physical identity or permission.
- The role builder uses the stale prior cashier ID as cashier_known, assigns the new non-cashier track outsider from the cashier half-plane, and emits PERSON_IN_CASHIER_ZONE. The rule consumes that2.5s sustained condition as A-OUTSIDER-ZONE@21.
- observed_entry=true is not independent evidence: it comes from door-region/boundary geometry. The new box partly overlaps the broad door region. The initial recording-start cashier also receives observed_entry=true, so this flag cannot repair this case by itself.
- No dynamic cashier-position update occurs here: the calibrated anchor is fixed (.621897,.509422). A new track is later selected as cashier from workstation/posture evidence. This is location being promoted to identity during fragmentation, not evidence of an anchor jump.

The trace supports a stale-ID/new-track explanation; it cannot prove whether person:19 is the same physical cashier, a ghost/reflection after lights-out, or another detection artifact. The human report supports no outsider; that label is evaluation evidence only. No IDs are merged and no physical identity is assigned by the candidate.

## Comparisons

| Input | In-room tracks (first–last s) | Separate cashier co-observation | A-OUTSIDER-ZONE before→after |
| --- | --- | --- | --- |
| originalX11 cached NN | person:1 0–16.5; person:21 17.5–20; person:22 21–23.5 | none for all3 | none→none |
| originalX12 cached NN | person:1 0–33.5; person:32 34.5–37; person:40 38–40.5 | none for all3 | none→none |
| mirroredX11 actual trace | person:1 0–20; person:19 21–23.5 | none | @21, actor19, duration2.5→removed |
| mirroredX12 actual trace | person:1 0–33.5; person:28 34.5–36.5; person:32 37.5–40.5 | none for all3 | none→none |

All four contain short outsider→cashier role transitions around lost/new tracks. Only mirroredX11 accumulates the sustained zone condition before reassignment. This does not turn any isolated track into a cashier by assumption. Original X11 runtime trace index also contains three existing original-video traces with no findings; paths/digests are in original-trace-index.json. No originalX12 runtime trace was found in that index; its comparison uses the requested frozen NN cache.

## Small unapplied candidate

candidate.patch changes only a_outsider_zone in backend/f1/rules.py: a finding's actor must have been observed, at or before its proposed timestamp, alongside a distinct nonempty cashier track ID. Missing role/identity evidence supplies no positive identity proof. No timing threshold, camera side, clip, filename, organizer marker, outcome, policy or legal citation enters the predicate.

Prior separate-actor evidence survives when the cashier later leaves. A new unobserved identity after cashier loss stays unsupported. The patch does not reassign or reconnect tracks, change calibration, change ENTER/EXIT events, suppress final exits, interpolate observations, or add any laptop/departure reason. It is a **rule evidence safeguard**, not a repaired tracker: raw location-based outsider labels remain unverified in the upstream trace/LLM context and must not be interpreted as established identity.

## Exact measured deltas

All40 cached CPU event/rule replay matches the requested baseline: **30/40 = TP11, TN19, FN10, FP0**, before and after. Existing scripts/replay_f1.py.score independently agrees. There are **zero original finding deltas, including all12 finding records**, and zero clean alarms out of19 clean clips. All original events remain untouched because the candidate only changes the outsider evaluator.

Supported examples remain exact:

- X30 A-OUTSIDER-ZONE@13, actor person:23, remains. It is co-observed with cashier person:10 from13s, unlike mirroredX11.
- X18 A-SECOND-PERSON@19.5, actor person:24, remains. Its client/actor entry and handover events are untouched.
- Every other rule's findings/facts/timestamps remain identical, not merely the aggregate verdicts.

On8 exact published mirror traces, the **only outsider-rule delta** is removal of mirroredX11 A-OUTSIDER-ZONE@21 with actor person:19 and condition duration2.5s. The other7 remain unchanged. This is existing-event/role rule replay, not full perception/event reconstruction: published frame records omit body/hands/raw per-sample state scores. The candidate needs only preserved track IDs, roles and sample times; no approximate boxes are used for identity proof.

The original mirrored API publication scored5/8 (TP1,FN3,TN4,FP0) solely because X11's wrong reason matched a violation verdict. Removing it makes the counterfactual verdict score **4/8 (TP0,FN4,TN4,FP0)**. That apparent reduction is deliberate and must not be hidden. X11's true violation cause remains unimplemented/unproven in this replay; no replacement reason is invented. A lack of supported findings does not establish that the clip is physically clean. This is neither new-angle nor held-out evidence.

## Validation actually run

One focused regression with the real mirroredX11 trace and synthetic identity controls passed: unsupported new-only track rejected; an actor previously observed alongside a separate cashier remains eligible even after that cashier disappears; a future-only co-observation cannot validate an earlier accusation. Synthetic controls are not model results.

All40 CPU cache replay and all8 trace rule replays completed. Existing replay scorer was reused. Ruff check passes after initial formatting and fragment-scope lint issues were corrected by embedding the candidate function in its pinned-module execution namespace. patch --dry-run -p1 against the read-only base succeeds; no patch was applied. Source rules digest still matches58c19c185c62ee054f5edf392629812458b363277f88c75c59f94868955a4324.

Exact argv/env/cwd are in cpu-command.json. From worker-2:

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 RULE_SCOPE=detector .venv/bin/python attempts/A26-person-context/replay.py --base /home/ubuntu/workspaces/datathon26-workers/shared/a23/base --cache /home/ubuntu/workspaces/datathon26-workers/shared/a22/perception_cache --publication /home/ubuntu/workspaces/datathon26-workers/shared/a23-mirrored-publication --out attempts/A26-person-context
```

## Limits / next probe

Real entrants visible only after the cashier leaves will now lack the required identity evidence; those cases need better tracking/observed-entry context instead of an outsider accusation. Co-observed duplicate/ghost tracks can still satisfy the gate, and an ID switch on an already distinguished track is not repaired. Legal authorization cannot be established merely by two actors and a zone. Upstream raw role labels are still location hypotheses.

Next local probe, if parent approves further work: preserve pre/post-association track diagnostics and raw NN pose confidence around generic illumination changes/track loss; check temporal overlap and competing actor evidence. Do not join IDs across an unobserved gap from proximity alone or use a low-light/recording-end exception. Parent decides whether to promote this safeguard or request a tracker fix. No GPU/model calls, pixels, new video run or broad suite were used here.
