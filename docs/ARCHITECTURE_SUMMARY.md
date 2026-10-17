# Architecture summary

Full detail and evidence: `reasearch1/architecture.md` (ADR-002) and
`reasearch1/architecture-decision.md`. This page is the short version for
task.md §8 ("краткое описание архитектуры, выбранного подхода и
используемых моделей").

## Approach

The service never lets a model decide the verdict. A vision-language model
(VLM) only fills in a fixed, schema-constrained per-frame "state form"
(is the cashier at the desk, is cash visible, is the safe door open, …). A
separate, deterministic rules engine — plain Python, no model — turns the
resulting state timeline into findings (persistence, durations, transitions
over a known list of mechanisms). A read-only Knowledge Pack then attaches
each finding's normative citation. The VLM never sees the rules, never
produces user-facing text, and never chooses a citation.

```
Client ──POST .mov──> API ──> Worker (1 GPU job at a time)
                                  │
                        probe + sampling plan (coarse 4s grid, then 2s fill)
                                  │
                              Detector
                       ┌──────────┴──────────┐
                 VLM (primary)          F1 CV stack (fallback)
          Qwen3.5-9B FP8 on vLLM     OWLv2 + CLIP + RTMPose + ByteTrack
             → per-frame state form        → same Finding shape
                       └──────────┬──────────┘
                            Findings (rule_id, t_anchor, support, facts)
                                  │
                        Rank + cap at 3 findings
                                  │
                    Knowledge Pack (knowledge/rules.yaml + norms.json)
                                  │
                      Evidence extraction (ffmpeg seek → JPEG)
                                  │
                      Serialize → jury contract (+ optional UI extras)
                                  │
                              GET /jobs/{id}
```

## Components

| Component | Role |
| --- | --- |
| FastAPI app (`backend/main.py`) | Auth (`X-API-Key`), upload validation, job store, `/healthz`/`/readyz` |
| Worker | One GPU job at a time (FIFO); other uploads queue |
| Preprocessing (`backend/media.py`, `backend/plan.py`) | `ffprobe` validation, coarse-then-fill sampling plan under a per-job deadline |
| Detector (`Detector` protocol, `backend/contracts.py`) | `VlmDetector` (primary) or `F1Detector` (fallback), selected by `DETECTOR=vlm\|f1` |
| Perception | Qwen3.5-9B FP8 on vLLM (loopback `:8010`), one schema-constrained question per sampled frame |
| Temporal rules (`backend/rules/`) | Pure function of the state timeline; no I/O, no learned weights, no access to ground truth |
| Knowledge Pack (`backend/knowledge.py`, `knowledge/`) | Deterministic `rule_id → norm_ids` lookup; marks a citation `needs_review` unless a human has verified it on adilet.zan.kz |
| Evidence (`backend/evidence.py`) | Cuts 1–3 JPEG frames from the *source* video at the finding's anchor time, never from the downsampled VLM input |
| Serializer | Maps the internal `GroundedFinding` to the jury's `Violation` shape, with the UI-only extras attached |

## Locality

Everything that touches video, frames or their descriptions runs on the
team's own host (`datathon2`, one NVIDIA L4 GPU) — no cloud AI API is called
during processing (task.md §7, FAQ 21). `vllm serve` is bound to
`127.0.0.1:8010` (loopback only) with `HF_HUB_OFFLINE=1`,
`VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1`. Model weights are downloaded once,
ahead of time, over the network; processing itself needs no internet access
(task.md §7, "переносимость"). Uploaded videos and sampled frames are
deleted when a job ends; the result JSON (with its embedded evidence frames)
is kept 24 h and then purged (`reasearch1/architecture.md` §8).

## Deadline and coverage behaviour

- Each job has a deadline of upload time + 270 s (a 30 s margin inside the
  jury's 300 s budget, for evidence extraction, serialization and polling).
- Sampling is coarse-first: a 4 s grid covers the whole video quickly, then
  2 s "fill" samples are added for as long as the estimated remaining time
  allows.
- At deadline − 15 s, the service stops issuing new frame requests and runs
  the rules on whatever completed. The job still finishes `done` in under
  300 s, but `coverage.mode` becomes `"partial"` (or stays `"coarse"` if the
  2 s fill pass never started), and the UI shows a visible warning
  (`docs/LIMITATIONS.md`, "sampling gap").
- A job that waited in the queue behind another upload starts with less
  remaining budget and gets a coarser plan under the same mechanism — not a
  separate code path.

## Fallback

If the primary VLM cannot serve (unreachable, out of memory, or over its
failed-frame threshold), the operator switches `DETECTOR=f1` and restarts:
a classical CV stack (OWLv2 scene/object grounding, CLIP crop-state
classification, RTMPose keypoints, ByteTrack tracking) that emits the same
`Finding` shape into the same rules/knowledge/evidence path. The two
detectors are never loaded on the GPU at the same time (`reasearch1/architecture.md`
§5).
