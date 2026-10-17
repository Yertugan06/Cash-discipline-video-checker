# Local models and licences

Only the pinned checkpoints below are loaded. They are downloaded explicitly by `scripts/download_weights.sh`; inference uses local files with Hugging Face offline mode and telemetry disabled.

| Purpose | Checkpoint | Checkpoint licence | Pinned revision |
| --- | --- | --- | --- |
| Person detection | [PekingU/rtdetr_r18vd](https://huggingface.co/PekingU/rtdetr_r18vd/tree/ac77a11ff0170a41b771c03264987f8ce2b0d753) | apache-2.0 | `ac77a11ff0170a41b771c03264987f8ce2b0d753` |
| Scene and object grounding | [google/owlv2-base-patch16-ensemble](https://huggingface.co/google/owlv2-base-patch16-ensemble/tree/cfd3195ba4ea9592eec887ded089f4c08eff231d) | apache-2.0 | `cfd3195ba4ea9592eec887ded089f4c08eff231d` |
| Crop state classification | [laion/CLIP-ViT-B-32-laion2B-s34B-b79K](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K/tree/1a25a446712ba5ee05982a381eed697ef9b435cf) | mit | `1a25a446712ba5ee05982a381eed697ef9b435cf` |
| Body and hand keypoints | [bukuroo/RTMPose-ONNX](https://huggingface.co/bukuroo/RTMPose-ONNX/tree/a6e9fb8a9190efd0383b059033f45645180cc7df) | apache-2.0 | `a6e9fb8a9190efd0383b059033f45645180cc7df` |

Checkpoint licence declarations were checked on their individual model cards, not inferred only from code repositories. Apache-2.0 and MIT permit commercial use. The OpenCLIP model card recommends domain-specific validation before deployment; it is not validated for this bank camera domain.

Weights use safetensors (RT-DETR, OWLv2, OpenCLIP) or ONNX (RTMPose). No unpickling or remote model code is enabled. Exact artifact sizes, source revisions and published weight SHA-256 values are in [models.lock.json](models.lock.json). The downloader verifies every weight and records hashes for every downloaded file in `weights/manifest.json`.

## Weight checksums

- `person/model.safetensors`: `fe87a5a30f5daf298d10794c7682a63b6107986f97d6a770ba948d89e4340093`
- `objects/model.safetensors`: `e1e130b9e404cf91a75ad45644c1da9d7fa5284085eecc864266a6923efb99e7`
- `states/model.safetensors`: `74813fbcdc750f235c9784c367ca1394d2a5c25eb0aac92761752ac239db7cff`
- `pose/rtmpose-m-wholebody.onnx`: `465259a2e6c0f434ec5a5097640d6a439106c423e942ddbab7c6eaa02cc00c8a`

## Tracking and inference libraries

ByteTrack is supplied by **Supervision 0.27.0 (MIT)**, using its local Kalman/IoU two-stage tracker; it performs no cloud inference and uses no appearance embeddings. [Pinned source licence](https://github.com/roboflow/supervision/blob/0.27.0/LICENSE.md).

PyTorch, torchvision, Transformers, OpenCV and ONNX Runtime execute locally. The CPU image uses PyTorch CPU wheels. `compose.gpu.yaml` uses CUDA 12.8 PyTorch wheels; RTMPose uses ONNX Runtime CPU by default. An installed CUDA ONNX provider is used when available, but it is not required. GPU runtime on the target PC remains to be measured.

## Privacy and unsupported models

No face recognition or identification is performed. RTMPose whole-body output is reduced to generic body points and hand points; its 68 detailed face landmarks are discarded. Head-region coordinates only support the cup/food action cue. There are no face crops for matching, face embeddings or identity databases.

Ultralytics and AGPL YOLO are not installed or used. No cloud AI inference service is called. Public model hosting is contacted only by the explicit download script, before offline processing. Video frames and descriptions are never sent to a model-hosting service.

The supplied model scores are similarity/detection scores, not calibrated probabilities of a legal breach. All legal references and report templates come from `codex.yaml`.
