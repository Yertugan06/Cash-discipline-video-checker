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

## Components

| Component | Role |
| --- | --- |
| FastAPI app (`backend/main.py`) | Auth (`X-API-Key`), upload validation, job store, `/healthz` and `/readyz` (weights present and matching `models.lock.json`) |
| Worker (`backend/worker.py`) | One job at a time from a FIFO queue; other uploads wait |
| Orchestration (`backend/pipeline.py`) | probe, plan, detect, rank, ground, evidence, serialize |
| Detector (`backend/f1/`) | Perception, calibration, events and rules described above |
| Rule thresholds (`config/f1_codex.yaml`) | Generated from `data/Cash_Discipline_Cases_Rules.xlsx` by `scripts/convert_codex.py` |
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

See `attempts/README.md`. The F1 stack was measured as A01 (20/40 correct
verdicts, 13/19 clean videos falsely flagged). The deployed service (A12)
has not been scored on all 40 videos yet.
