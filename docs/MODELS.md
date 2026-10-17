# Models and licences

**Re-check every model card below against the live Hugging Face page before
submission (task.md §8, G4 checklist item 10).** Licence notes here were
read from the cards on 2026-10-17 and are marked `[Rep]` (reported) where
this team did not independently re-verify them today.

Only one detector is loaded on the GPU per deployment, selected by the
`DETECTOR` environment variable (`backend/config.py`). Switching detectors
means a restart, never running both at once (`reasearch1/architecture.md` §5).

## Primary path: `DETECTOR=vlm`

| Purpose | Checkpoint | Serving | Licence |
| --- | --- | --- | --- |
| Perception (per-frame state form) | **Qwen3.5-9B**, FP8 quantized | vLLM, loopback `127.0.0.1:8010`, offline mode | Apache-2.0 `[Rep]` |

The model is only a perceiver: for each sampled frame it fills a fixed JSON
form (`backend/contracts.py:FrameState`) with directly observable fields
(is the cashier at the desk, is the safe door open, …). It never produces
free text that reaches the user, never decides a verdict, and never chooses
or states a legal citation — that is the deterministic rules engine's job
(`docs/ARCHITECTURE_SUMMARY.md`).

### Fallback L2 (timing/licence contingency): `Qwen3-VL-4B`

Same serving path and same state-form contract as the 9B model, swapped in
only if the 9B cannot meet the per-job timing budget or a licence check
fails close to the deadline (`reasearch1/architecture.md` §6, "Trade-off
levers"). Apache-2.0 `[Rep]`. Never loaded alongside the 9B.

## Fallback L3: `DETECTOR=f1`

A classical computer-vision stack, used only if neither VLM option is
viable at deploy time:

| Purpose | Checkpoint | Licence | Pinned revision |
| --- | --- | --- | --- |
| Person detection | [PekingU/rtdetr_r18vd](https://huggingface.co/PekingU/rtdetr_r18vd/tree/ac77a11ff0170a41b771c03264987f8ce2b0d753) | apache-2.0 | `ac77a11ff0170a41b771c03264987f8ce2b0d753` |
| Scene/object grounding | [google/owlv2-base-patch16-ensemble](https://huggingface.co/google/owlv2-base-patch16-ensemble/tree/cfd3195ba4ea9592eec887ded089f4c08eff231d) | apache-2.0 | `cfd3195ba4ea9592eec887ded089f4c08eff231d` |
| Crop state classification | [laion/CLIP-ViT-B-32-laion2B-s34B-b79K](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K/tree/1a25a446712ba5ee05982a381eed697ef9b435cf) | mit | `1a25a446712ba5ee05982a381eed697ef9b435cf` |
| Body/hand keypoints | [bukuroo/RTMPose-ONNX](https://huggingface.co/bukuroo/RTMPose-ONNX/tree/a6e9fb8a9190efd0383b059033f45645180cc7df) | apache-2.0 | `a6e9fb8a9190efd0383b059033f45645180cc7df` |
| Tracking | ByteTrack via Supervision 0.27.0 | MIT | pinned `0.27.0` |

Checkpoint licences were checked on their individual model cards, not
inferred only from code repositories; Apache-2.0 and MIT both permit
commercial use. The OpenCLIP model card recommends domain-specific
validation before deployment; it has not been validated for this bank
camera domain. Weights use safetensors (RT-DETR, OWLv2, OpenCLIP) or ONNX
(RTMPose); no unpickling or remote model code is enabled. Exact artifact
sizes, source revisions and weight SHA-256 hashes are recorded by
`scripts/download_weights.py` in `weights/manifest.json`. **This stack has
not beaten the floor baselines on the full 40-video run and is kept only as
an emergency fallback** (`reasearch1/architecture-decision.md` §3-4).

## Infrastructure / tooling

| Library | Role | Licence |
| --- | --- | --- |
| vLLM | Serves the VLM | Apache-2.0 |
| FastAPI, Pydantic, uvicorn | Backend | MIT |
| React, TypeScript, Vite | Frontend | MIT |
| ffmpeg | Video probing and frame extraction (separate process, system package) | LGPL/GPL depending on build — not redistributed, only invoked as a subprocess |
| PyTorch, Transformers, OpenCV, ONNX Runtime | F1 fallback runtime | BSD/Apache-2.0 |

## Privacy

No face recognition or identification is performed anywhere in either
detector path (task.md FAQ 29). The F1 stack's pose keypoints are reduced to
generic body/hand points; no face crops, face embeddings or identity
database exist. Video frames and their VLM-produced descriptions never
leave the deployment host (`docs/ARCHITECTURE_SUMMARY.md`, "Locality").
