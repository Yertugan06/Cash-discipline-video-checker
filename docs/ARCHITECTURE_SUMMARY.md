# Architecture summary

The short version for task.md §8 ("краткое описание архитектуры, выбранного
подхода и используемых моделей"). It describes the detector that is actually
deployed: the F1 computer-vision stack (`DETECTOR=f1`, the default in
`backend/config.py`). The earlier VLM-first version of this page is kept in
`archive/docs-vlm-era/ARCHITECTURE_SUMMARY.md`; the design records behind it
are `archive/research1/architecture-decision.md` (ADR-002) and
`archive/research1/architecture.md`.

## Approach

No model decides the verdict. Pretrained detectors only report what is in
each frame (people, objects, door/safe/screen states, hand keypoints). A
deterministic event builder turns those observations into a timeline of
events (cashier left the desk, cash on desk, someone entered, door closed,
...), and plain-Python temporal rules turn the event timeline into findings.
A read-only Knowledge Pack attaches each finding's normative citation. The
verdict is `violation` if and only if at least one finding survives.

```
Client --POST .mov--> API --> Worker (1 GPU job at a time, FIFO)
                                  |
                       ffprobe + per-job deadline (270 s)
                                  |
                 F1Detector (backend/f1/detector.py)
   frames at 2 fps (0.5 s step), decoded with ffmpeg
                                  |
   perception (backend/f1/perception.py, config/perception.yaml)
     RT-DETR r18vd   people
     OWLv2           scene objects (desk, laptop, safe, door, counter)
                     and small objects (cash, documents, bags, ...)
     OpenCLIP B-32   crop states (door open/closed, safe open, ...)
     RTMPose         hand / body keypoints
     ByteTrack       person tracks
                                  |
   calibration (backend/f1/calibration.py): first 2 s -> desk, laptop,
     safe, door zones; cashier / client half-planes around the desk
                                  |
   events (backend/f1/events.py): ENTER, EXIT, PERSON_IN_CASHIER_ZONE,
     PERSONAL_ON_DESK, SAFE_UNATTENDED, COUNT_START, HAND_ON_*, ...
     with hysteresis
                                  |
   rules (backend/f1/rules.py): one function per rule id, thresholds
     from config/f1_codex.yaml; findings for ids that are not in
     knowledge/rules.yaml are dropped
                                  |
                 Rank + cap at 3 findings (backend/rules/ranking.py)
                                  |
          Knowledge Pack (knowledge/rules.yaml + knowledge/norms.json)
                                  |
   Evidence (backend/evidence.py): 1-3 JPEGs cut from the source video,
     with the triggering object's box drawn on the anchor frame
                                  |
          Serialize -> jury contract (+ optional UI extras)
                                  |
                           GET /jobs/{id}
```

## What the rules rely on

The event builder and rules were reworked on 2026-10-18 (attempt A20,
`attempts/A20-night-orchestration/`). Each behaviour below is a mechanism with a unit test, not a
threshold fitted to one clip:

| Area | Behaviour |
| --- | --- |
| Scene scale | Distances (hand reach, laptop reach, glass and service margins) are multiples of the calibrated desk length, not fixed fractions of the image, so a camera nearer or farther gives the same events |
| Workstation presence | The cashier counts as at the workstation while a confident hand is inside the laptop or money-counter box, even when the hips are farther away |
| Leaving | An item counts as left behind only if it is seen in at least 2 frames of each short evidence window and the cashier stays away through the confirmation delay. A cash bag counts for `L-NO-CASH-ON-LEAVE` |
| Entries | Someone already in the doorway in the first frame has not entered; the door rule needs an observed entry |
| Client sessions | A client whose track is lost and reappears in place within the exit gap is the same client; a client exit needs visible movement away from the desk; two clients with hands on the desk at once, held, is a second client; the counter still running when the client leaves is counting without the client |
| Personal items | Brief detection gaps don't split one item; boxes that match the laptop or the money counter are equipment, not personal items; a small coat box above the person's hip line is worn clothing |
| Cash collection | `K-SEAL-CHECK` fires when a visitor with an observed entry delivers a bag that appears on the desk and leaves quickly, without staying for the check |
| Ranking | Among equal findings, the one with a confirmed exit ranks first, so the top timecode is the moment the cashier is really gone |

## Components

| Component | Role |
| --- | --- |
| FastAPI app (`backend/main.py`) | Auth (`X-API-Key`), upload validation, job store, `/healthz` and `/readyz` (weights present and matching `models.lock.json`) |
| Worker (`backend/worker.py`) | One job at a time from a FIFO queue; other uploads wait |
| Orchestration (`backend/pipeline.py`) | probe, plan, detect, rank, ground, evidence, serialize |
| Detector (`backend/f1/`) | Perception, calibration, events and rules described above |
| Rule thresholds (`config/f1_codex.yaml`) | `rules` generated from `knowledge/rulebook.yaml` by `scripts/build_knowledge.py` |
| Knowledge Pack (`backend/knowledge.py`, `knowledge/`) | Rule lifecycle and deterministic `rule_id -> norm_ids` lookup; citations carry KZ document metadata and `verified`/`pending`/`invalid` status. F1 startup checks codex, evaluator IDs, and enabled rules. Built by `scripts/build_knowledge.py` |
| Evidence (`backend/evidence.py`) | Frames from the original video at the finding's anchor time, never from the detector's sampled frames |
| Serializer (`backend/serialize.py`) | Maps `GroundedFinding` to the jury's `Violation` shape |
| Live gateway (`realtime/`) | Optional: feeds a folder of videos through the API one by one and streams verdicts over a WebSocket |

## Locality

Every model runs on the team's own host (`datathon`, one NVIDIA L4) from
weights downloaded ahead of time (`scripts/download_weights.py`, pinned in
`models.lock.json`). Hugging Face offline mode is forced in
`backend/f1/perception.py`, so processing needs no internet access and no
cloud AI API is called (task.md §7, FAQ 21). The service binds to
`127.0.0.1:8000`. Uploaded videos and sampled frames are deleted when a job
ends; result JSON is kept for `RESULTS_TTL_HOURS` (24 h by default) and then
purged.

## Deadline and coverage

- Each job has a budget of 270 s (`JOB_BUDGET_S`), a 30 s margin inside the
  jury's 300 s limit.
- F1 samples the whole video uniformly at 2 fps. Coverage is reported as
  `mode="full", step_s=0.5`; if the budget runs out before perception
  finishes, `coverage.deadline_hit` is `true`.
- Perception results are cached per video checksum
  (`Settings.reuse_perception`, on by default), so re-running the same
  video skips inference.

## Alternative detector (not deployed)

`DETECTOR=vlm` switches perception to a vision-language model (Qwen3.5-9B
FP8 on vLLM, `backend/vlm/`, `deploy/vllm/`) that fills a per-frame state
form, followed by the timeline rules in `backend/rules/timeline.py`. Its
code and tests are kept, but it is not what runs on `datathon`; see
`archive/docs-vlm-era/` for that design.

## Measured results

Offline replay on the cached perception of the 40 unique open videos, scored against the
organizer labels (`attempts/A20-night-orchestration/`):

| Version | Correct /40 | Clean videos flagged /19 | Violations missed /21 |
| --- | --- | --- | --- |
| A01, the F1 stack before it was ported into this service | 20 | 13 | 7 |
| A17, deployed on `datathon` before A20 | 25 | 5 | 10 |
| **A20, this version** | **32** | **0** | **8** |

- **Timecodes:** 13 caught violations; mean distance to the organizer second 1.54 s; within
  ±1 / ±3 / ±5 s: 7 / 11 / 13.
- **Robustness probes** (`scripts/replay_f1.py run --zoom/--mirror/--drop`, the clips replayed
  as another camera distance, a mirrored camera or a weaker detector): zoom 0.7-1.3 and mirror
  give exactly 32/0/8; losing 20% of object detections gives 31-32 / 0 / 8-9.
- All 40 videos were also used while building A20, so expect less on new videos. The 8 misses
  are listed in `docs/LIMITATIONS.md`.
