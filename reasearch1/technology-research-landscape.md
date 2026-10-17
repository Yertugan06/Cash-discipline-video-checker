# Video compliance detection: solution landscape

Research status, 17 October 2026: I found usable local models and video components, but no verified, commercially usable system pretrained to identify bank cash handling procedure violations. The strongest near-term options are video language models for discovering candidate events, visual detectors and trackers for checking specific observable actions, and embedding models for finding similar moments. None supplies the bank’s rules or proves a violation on its own.

The dataset is especially small for training a new action taxonomy: 40 unique videos, including 21 violation and 19 clean videos, with timestamps but no violation types. Published scores on movie actions, web videos, or crime surveillance should therefore be treated as evidence that software runs, not as an estimate of performance on these videos. For example, AVA labels atomic actions in movies; HICO-DET labels human–object interactions in still images; and UCF-Crime covers events such as robbery and vandalism, not procedural handling of cash.

## A. Solution landscape

| Family | What it can contribute | Fundamental limit here |
|---|---|---|
| A. Local video VLMs | Describe a clip, compare a sequence with a written rule, propose an event and time. Native video input still samples or encodes frames. | Small hand actions may disappear at the chosen frame rate; generated descriptions and timestamps need visual verification. |
| B. Image VLMs over sampled frames | Inspect high-resolution crops of hands, counter, documents, and objects. Useful for checking a proposed event. | A single frame often cannot establish transfer, sequence, or omission. |
| C. Action recognition and temporal localization | Produce action scores or time intervals from video features. | Pretrained labels rarely include bank procedures; localization models often expect training for the target action classes. |
| D. Detection, tracking, and temporal rules | Track people and objects across counter zones; preserve frame-level evidence. | Cash is small and visually similar to paper. A tracked movement has no inherent legal meaning. |
| E. Human–object interaction (HOI) | Identify relations such as a person holding or passing an object. | Most available checkpoints operate on still images and use everyday objects and verbs. |
| F. Video anomaly detection | Flag unusual intervals without naming every mechanism in advance. | “Unusual” is not the same as prohibited. Staged clean and violation clips may share the same visual style. |
| G. Vision–language embeddings | Rank video windows against text descriptions or labeled examples quickly. | Similarity scores do not prove an event or give a justified verdict. |
| H. Hybrid visual evidence and explicit rules | Connect an observed event, its time and frames, and a separately sourced rule. | Depends on accurately perceiving the event and obtaining the actual normative text. This is an approach to test, not a selected architecture. |

A practical distinction runs through all eight families: event discovery must search the whole video without being given the supplied violation timestamp. The timestamp can be used afterward to score localization.

## B. Candidate inventory

“Weights available” means a checkpoint or documented download is present; it does not mean I ran it. License entries distinguish published code and weight terms where the sources allow it. Runtime and peak VRAM for your videos are unmeasured.

| Candidate and kind | Input, capability, and grounding | Weights, license, and practical assessment |
|---|---|---|
| Qwen3-VL-4B-Instruct — foundation model | Native image/video interface; model card claims timestamp-aligned video understanding. Can describe fine actions, but bank HOI reliability is unverified. Zero-shot prompts and local Transformers examples are documented. | 4B, BF16; weights available; Apache 2.0 listing. About 8 GB for BF16 parameters alone, before vision processing and runtime memory; actual GPU fit and 10–145 s latency need measurement. Strong first video VLM test. |
| Qwen3-VL-2B-Instruct — foundation model | Same video interface and temporal claims at smaller scale; may permit more windows or denser sampling. Exact timestamp and small-object quality are unverified. | 2B, BF16; weights available; Apache 2.0 listing. Roughly 4 GB of BF16 parameters alone, not a VRAM requirement. Good speed/quality comparison with 4B. The card includes local inference examples. |
| Qwen2.5-VL-7B-Instruct — foundation model | Native video input with frame sampling and timestamps; established local inference examples. Fine hand and object recognition remains an empirical question. | 7B; weights available; Apache 2.0 listing. Approximately 14 GB for BF16 parameters alone plus substantial runtime overhead. Attractive quality comparator if hardware permits; full-video five-minute feasibility is unmeasured. |
| VideoLLaMA3-2B and code — foundation model | Video-to-text model with documented local inference; processes video frames. Can describe events, but precise compliance judgments and timestamps are unverified. | 2B; weights available; model and code list Apache 2.0. Uses custom model code. Plausible local alternative if Qwen installation or throughput disappoints; integration burden is higher. |
| LLaVA-NeXT-Video-7B-hf — foundation model | Video question answering from frames; runnable Transformers example. Temporal answers are possible but precise boundaries and fine bank interactions are unverified. | 7B; weights available. Model card cites the Llama 2 Community License, so commercial terms require separate review. Older comparison candidate, below the Apache-listed options. |
| Grounded-Video-LLM — research prototype | Designed for text-query temporal grounding; inference scripts and checkpoints are linked. Its question is “when did this described action occur?”, which requires the action description first. | Authors recommend 24 GB GPU for the Phi-3.5 version, 32 GB for the 8B version. Repository licensing was not verified, and base-model terms also apply. Valuable localization reference; unlikely to be the first hackathon integration. |
| Florence-2-base — image foundation model | Image captioning, detection and grounding on individual frames or crops; no native temporal reasoning. Useful for testing whether small objects and hand regions can be described or located. | 0.23B; weights available; MIT weight license. Runnable Transformers examples. Relatively light, but cannot establish an event sequence alone. |
| Grounding DINO tiny and code — detector | Text-prompted object boxes per frame; temporal intervals require tracking. “Cash”, “paper”, and similar prompts must be tested on actual overhead images. | Weights available; model listing and code Apache 2.0. Good reusable detector with documented local inference. Tiny targets and prompt sensitivity are the central risks. |
| SAM 2 — video segmentation component | Tracks prompted masks through video and provides frame-level object evidence. It does not identify a violation or discover the relevant object without a prompt. | Checkpoints, code, and notebooks are provided under Apache 2.0. GPU memory and speed depend on checkpoint and frame count; measure before using over entire videos. |
| SigLIP2 base patch16 224 — embedding model | Zero-shot image/text similarity. Applied to sampled frames or crops, so time comes from sampling; no native event sequence or normative reasoning. | Weights and local examples available; Apache 2.0 listing. Checkpoint file is about 1.5 GB. Promising cheap retrieval baseline, especially for prioritizing windows. |
| InternVideo2 Stage2 1B 224p f4 and code — video embedding model | Video/text retrieval and zero-shot similarity using short frame sets; native video representation, but no rule verdict. Local setup is more involved than SigLIP2. | Checkpoint listed under Apache 2.0, code under Apache 2.0. Its demo guide documents additional model setup. Hardware and end-to-end runtime are unverified. |
| X3D-XS in PySlowFast — action backbone | Efficient video classification on short clips; sliding windows can give coarse times. Fixed pretrained action vocabulary has little direct cash-handling coverage. | Official model zoo links weights and lists 3.8M parameters for X3D-XS. Code is Apache 2.0; separate checkpoint permissions need confirmation. Faster-looking baseline, but likely needs target labels. |
| ActionFormer — temporal localizer | Predicts intervals for trained action classes from pre-extracted video features. Official examples use THUMOS, ActivityNet and EPIC-Kitchens features; it is not a ready detector for novel bank violations. | MIT code, linked pretrained task checkpoints. The authors report some EPIC/Ego4D inference configurations may need over 10 GB and recommend 12 GB. Feature extraction and class transfer are major integration costs. |
| GEN-VLKT — HOI research prototype | Still-image person–object interaction predictions; frame sampling is needed for video, with no built-in temporal grounding. | MIT code and linked HICO-DET/V-COCO checkpoints. Documentation is detailed, but setup includes older dependencies; its object and verb classes may miss bank-specific interactions. |
| VadCLIP — anomaly research prototype | Window anomaly scoring from CLIP features; can suggest times but cannot establish a rule violation. It is trained for UCF-Crime/XD-Violence style anomaly tasks. | Apache 2.0 code; repository links features and pretrained models. Checkpoint terms beyond the repo and the full feature-extraction path need verification. Weak primary choice for subtle procedure errors. |

The largest licensing traps are specific, not theoretical: Qwen2.5-VL-3B-Instruct uses a research-only weight license, despite the related 7B listing being Apache 2.0; the popular VideoMAE Kinetics checkpoint and TimeSformer K400 checkpoint are marked CC BY-NC 4.0. Those are poor commercial-use defaults. Ultralytics YOLO code and models carry AGPL 3.0 obligations unless an enterprise license is obtained. A repository’s permissive code license should never be substituted for its checkpoint’s terms.

## C. Shortlist for empirical evaluation

This ranks experiments, not a final architecture.

1. Qwen3-VL-4B-Instruct. Best combination found of local video input, current runnable documentation, Apache-listed weights, and a manageable model size. Test whether it finds events without being told their time, whether cited frames support its descriptions, and whether it fits the deadline.
2. Qwen3-VL-2B-Instruct. The same style of test at lower compute cost. It may allow denser temporal coverage; whether that offsets weaker perception is unknown.
3. Grounding DINO tiny with local tracking tools. Tests the key physical assumption: can relevant people and objects be detected consistently enough for observable handoffs and zone transitions? This deserves testing even if a VLM appears persuasive.
4. SigLIP2 base. Fast candidate-window retrieval baseline. Its value is measurable without asking it to write a compliance judgment.
5. Qwen2.5-VL-7B-Instruct, conditional on available GPU. A useful independent VLM comparator with Apache-listed weights. Skip the full experiment if loading or a pilot window already makes five minutes implausible.

VideoLLaMA3-2B is a reasonable substitute for candidate 5 when memory or Qwen-specific setup is the constraint. The published Grounded-Video-LLM grounding results justify looking at its methods, but its hardware recommendation and unresolved licensing make it a poor first integration.

## D. Existing solutions worth reusing

Components with permissive published licenses

- Roboflow Supervision provides video iteration, detections, tracking support, zones, annotations and frame output under MIT. Its tracking example also makes the detector’s separate license explicit. It can save plumbing time while keeping all processing local.
- Grounded SAM 2 combines local Grounding DINO with SAM 2 in a custom-video tracking example. This is substantial reusable object-tracking code, not a cash-compliance solution. Select the local Grounding DINO script: other examples in the same repository use API tokens and are unsuitable for organizer footage. Its own documentation warns that a simple demo initializes objects on the first frame and that continuous discovery is still unstable.
- MMAction2 provides documented video decoding, action recognition, localization, detection demos, and model-zoo integrations under Apache 2.0. Its value is infrastructure; its pretrained labels are not bank rules.
- MMDetection offers Apache 2.0 detection tooling and documented checkpoint inference.
- Frigate, under MIT, is a comparatively complete surveillance product with tracked objects, zones, review periods, and snapshots. It illustrates useful event/evidence mechanics, but adapting the whole product in 24 hours looks expensive.

Research prototypes and potentially disallowed ready-made solutions

- ActionFormer, GEN-VLKT, VadCLIP, and IndustReal’s procedure-step baseline offer methods or components. IndustReal concerns industrial, egocentric assembly rather than overhead banking footage.
- Factory Compliance System and a UCF-Crime surveillance API/UI project present more of an end-to-end solution. Their claims, dependencies, footage handling and licenses would need separate audit. The FAQ’s distinction between allowed pretrained models and disallowed ready-made solutions is unresolved; copying a complete compliance application is an organizer-eligibility risk.
- Kaggle has UCF-Crime datasets and notebooks, but they do not resolve this task’s rule semantics. One surveillance anomaly notebook explicitly uses a Gemini API and cannot be reused for inference under your privacy constraint. The cited UCF-Crime Kaggle copy lists its dataset license as unknown.

Hugging Face Spaces can help inspect demos and examples, but they must not receive organizer videos, frames, or descriptions. Downloading approved weights and running them locally is a different operation.

## E. Experiment backlog

Use the 40 unique videos as the unit of evaluation; keep duplicates together. Before scoring, record every model’s input frame rate, crop policy, prompt, threshold, and runtime. Use violation timestamps only as ground truth, never to choose the model’s input window. Because the camera change is a known risk, report that video separately and keep it out of threshold tuning. These are proposed gates, not claims that any model will reach them.

| Priority and hypothesis | Smallest test and required inputs | Measures and falsification criterion | Compute and effort estimate |
|---|---|---|---|
| 1. Qwen3-VL-4B can discover visible violations | Run local inference on a small, balanced set of whole videos, including clean clips, with fixed temporal sampling and an instruction to report uncertain observations. Review its proposed times and evidence without showing it labels. | Video-level precision/recall; event recall within a declared time tolerance; proportion of claims supported by cited frames; median and worst video runtime. Falsify if it misses short events at workable sampling or repeatedly states unsupported actions. | GPU with materially more than the ~8 GB BF16 parameter minimum; actual requirement unknown. Roughly 2–4 developer hours including download and scoring setup. |
| 2. Qwen3-VL-2B trades quality for denser coverage | Repeat experiment 1 on the same videos, prompts, sampling policy, and evaluation. Then use any measured speed headroom for a second, denser-sampling pass. | Same measures, plus gain per unit of processing time. Falsify if increased coverage does not recover events or if fine object descriptions become unreliable. | Lower parameter footprint; runtime unknown. 1–2 hours after experiment 1 harness exists. |
| 3. Grounding DINO tiny can expose rule-relevant objects and transfers | On locally selected frames across entire videos, prompt for people, hands and candidate objects; inspect detections and track only the best-defined objects. Do not use labeled times to select frames for discovery scoring. | Detection recall on a small manually annotated frame set, track continuity, false cash/paper detections, and time to process the longest video. Falsify if cash-related objects are usually too small or confused to support a temporal rule. | Local GPU desirable; exact VRAM unknown. 2–4 hours, potentially more if object taxonomy or tracking is unstable. |
| 4. SigLIP2 can rank candidate windows above clean activity | Sample windows uniformly, embed frames/crops locally, compare fixed text descriptions or a few labeled exemplars, and rank windows. Hold out videos when using exemplars. | Recall among top-ranked windows, false-positive windows per clean video, robustness on changed camera, runtime. Falsify if ranking is indistinguishable from scene or actor appearance. | Modest GPU relative to generative VLMs; exact runtime unknown. 1–3 hours. |
| 5. Qwen2.5-VL-7B improves visual evidence enough to justify cost | Run the same predeclared subset and metrics as experiment 1 if a pilot fits GPU memory and a feasible time budget. | Incremental event recall and evidence accuracy at equal sampling, plus worst-case runtime. Falsify if gains are small, claims remain unsupported, or a 145-second video cannot stay under five minutes. | Larger GPU needed; no verified peak VRAM or latency. 1–2 hours after common harness, excluding downloads. |

A useful scoring sheet should also separate event observed, time localized, violation type correct, and rule correctly applied. A binary correct answer with a fabricated explanation should fail the evidence and normative checks. With only 21 violation videos, show counts and per-video errors alongside percentages; a one-video change moves recall substantially.

## F. Decision matrix

Qualitative expectations below are hypotheses to test, not measured results.

| Candidate/family | Likely effectiveness on this footage | Five-minute feasibility | Compute | New violation types | Main uncertainty |
|---|---|---|---|---|---|
| Qwen3-VL-4B video | Medium to high potential | Plausible, unmeasured | Medium–high | Better than fixed-label classifiers | Whether sampled frames capture decisive hand actions |
| Qwen3-VL-2B video | Medium potential | More plausible, unmeasured | Medium | Some open-ended coverage | Fine object perception |
| Qwen2.5-VL-7B video | Medium to high potential | Hardware dependent | High | Some open-ended coverage | Added quality versus runtime |
| Grounding DINO + tracking + tested rules | High for visible, well-defined transfers; low for unseen mechanisms | Plausible if sampling is limited | Medium | Low without new rules | Detecting cash and maintaining identity |
| SigLIP2 window retrieval | Medium as a search aid; low as sole judge | Likely easiest to meet, unmeasured | Low–medium | Limited by prompts/examples | Correlation with setting rather than action |
| ActionFormer or fixed-label recognition | Low as a pretrained verdict engine | Feature extraction dominates | Medium–high | Low | No suitable pretrained bank classes |
| HOI still-image models | Low–medium as supporting evidence | Plausible on selected frames | Medium | Low–medium | Missing bank object/verb vocabulary |
| Generic video anomaly detection | Low as a compliance judge | Varies | Medium | Can flag novelty, not its meaning | False alarms and no normative justification |

## Failure modes to watch

| Failure | Perception, temporal, or normative? | Most exposed approaches |
|---|---|---|
| A brief hand movement falls between sampled frames | Temporal sampling | Video VLMs, image VLMs, embeddings |
| Cash looks like a receipt or other paper from above | Visual perception | Detectors, HOI, all VLMs |
| Hands or objects are hidden by another person | Visual perception and tracking | Detection/tracking, HOI |
| Two people touch or exchange the same object | Identity and temporal association | Tracking, action localization |
| A permitted and prohibited action look alike in isolation | Temporal context and normative interpretation | Still-image methods, generic classifiers |
| A required action never occurs | Temporal coverage and normative reasoning | All methods; especially short-window classifiers |
| A new violation mechanism appears | Open-set discovery | Fixed-label classifiers and hand-written rules |
| The final camera angle changes apparent size or zones | Visual distribution shift | Detectors, embeddings, learned position rules |
| An action is seen correctly but attached to the wrong policy | Normative reasoning | Generative VLMs and any system using unverified rule text |

The model should not invent a policy citation. The normative justification requires the organizers’ actual rules and a mapping from an observed, supported action to the applicable clause.

## G. Research gaps that require local evidence or organizer answers

1. Actual violation mechanisms and rule text. The dataset has timestamps but no types; no internet model card can identify the organizers’ intended interpretation.
2. Image geometry. Resolution, frame rate, compression, duration distribution, object pixel sizes, occlusion, and whether evidence survives cropping determine model choice.
3. Available hardware. GPU model, VRAM, disk for checkpoints, decoding speed, and concurrent request requirement determine whether any candidate meets five minutes.
4. Novelty and camera shift. The unseen types and final camera angle require held-out local tests; generic benchmarks cannot predict them.
5. Annotation tolerance. Whether a timestamp must mark onset, peak evidence, or a range, and how multiple violations are scored, affects experiments.
6. Eligibility and licensing interpretation. Ask organizers where they draw the line between an allowed pretrained model or library and a disallowed ready-made compliance solution. Confirm any checkpoint whose weight license is unclear before relying on it.

Recommended next research step: inspect and annotate a small, representative set of the organizer videos and obtain the written procedure clauses, then run the first two whole-video experiments. That evidence will support an architecture decision; the internet search alone cannot.