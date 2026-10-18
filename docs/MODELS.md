# Models and licences

**Re-check every model card below against the live Hugging Face page before
submission (task.md §8, G4 checklist item 10).** Licence notes here were
read from the cards on 2026-10-17 and are marked `[Rep]` (reported) where
this team did not independently re-verify them today.

The top-level detector is selected by `DETECTOR`. The current A21 service uses F1
and a separate local Qwen safe-state helper on the **same L4 VM**. The helper is
`F1_VISUAL_CHECKS=1`; it is distinct from the alternative `DETECTOR=vlm` pipeline.

## Deployed path: `DETECTOR=f1`

F1 is the default in `backend/config.py`. A21 runs on datathon2; the last recorded
public A20 deployment is on datathon. These models generate observations, while
deterministic rules, descriptions and the Knowledge Pack produce findings:

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
`scripts/download_weights.py` in `weights/manifest.json`. Current A21 verdict agreement
is 30/40, 0/19 clean false alarms, 10/21 misses. Historical A20 scored 32/40 with two
contradicted explanations. These public-development results do not establish unseen accuracy.

## Enabled A21 local helper: Qwen3-VL-4B-Instruct

`backend/f1/visual_checks.py` runs [Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)
in a local offline Transformers subprocess, bf16 on the same VM. Safe-state checks are
selected from observed events/movement; known answers refine exact samples and retain
provenance. Unknown answers do not prove absence. Cash/ID recognition is not supplied;
door answers remain diagnostic and the current enabled family is `safe` only.

The generic settings default to off; the A21 launcher defaults to **on at the user's request**.
It uses `F1_VISUAL_MODEL_PATH`, `F1_VISUAL_WORKER_PYTHON` and `F1_VISUAL_CACHE_DIR`.
The measured worker environment is Transformers 5.20.1, Accelerate 1.15.0 and PyTorch 2.11.0
with CUDA. The F1 environment is separate and unchanged. No vLLM server is needed.

The local 4B checkpoint's upstream commit was not recorded; do not describe it as revision-
pinned in `models.lock.json`. Model file identity/inventory, prompt and frame hashes are
captured in probe/cache artifacts. Licence is reported as Apache-2.0; recheck the linked card
before submission. The enabled run made 40 fresh calls and reused 476 answers, with no
verdict improvement. [Measured report](../attempts/A21-deadline/RESULTS.md).

## Alternative path, not deployed: `DETECTOR=vlm`

Kept in code (`backend/vlm/`, `deploy/vllm/`) and tests, but not what runs
on `datathon`. Design notes: `archive/docs-vlm-era/`.

| Purpose | Checkpoint | Serving | Licence |
| --- | --- | --- | --- |
| Perception (per-frame state form) | **Qwen3.5-9B**, FP8 quantized | vLLM, loopback `127.0.0.1:8010`, offline mode | Apache-2.0 `[Rep]` |

The model is only a perceiver: for each sampled frame it fills a fixed JSON
form (`backend/contracts.py:FrameState`) with directly observable fields
(is the cashier at the desk, is the safe door open, …). It never produces
free text that reaches the user, never decides a verdict, and never chooses
or states a legal citation - that is the deterministic rules engine's job
(`archive/docs-vlm-era/ARCHITECTURE_SUMMARY.md`).

### Historical smaller option for the alternative pipeline

This describes the older alternative design, not the enabled A21 subprocess helper.
It uses the same serving path and state-form contract as the 9B model, swapped in
only if the 9B cannot meet the per-job timing budget or a licence check
fails close to the deadline (`archive/research1/architecture.md` §6, "Trade-off
levers"). Apache-2.0 `[Rep]`. Never loaded alongside the 9B.

## Infrastructure / tooling

| Library | Role | Licence |
| --- | --- | --- |
| vLLM | Serves the VLM (alternative path only) | Apache-2.0 |
| FastAPI, Pydantic, uvicorn | Backend | MIT |
| React, TypeScript, Vite | Frontend | MIT |
| ffmpeg | Video probing and frame extraction (separate process, system package) | LGPL/GPL depending on build — not redistributed, only invoked as a subprocess |
| PyTorch, Transformers, OpenCV, ONNX Runtime | F1 runtime | BSD/Apache-2.0 |

## Privacy

No face recognition or identification is performed anywhere in either
detector path (task.md FAQ 29). The F1 stack's pose keypoints are reduced to
generic body/hand points; no face crops, face embeddings or identity
database exist. Video frames and their VLM-produced descriptions never
leave the deployment host (`docs/ARCHITECTURE_SUMMARY.md`, "Locality").
