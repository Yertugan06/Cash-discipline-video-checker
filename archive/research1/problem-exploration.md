# Problem Exploration — Datathon 26 (ForteBank): solution space, risks, hypotheses, experiments

Input: `task.md` (brief + FAQ), `problem-reframing.md` (rev 5). This document maps the solution space and plans the experiments that will choose among them. **It does not choose an architecture.** That happens after the experiments in §8, in `/problem-validate`.

**Evidence labels:** **[M]** measured here · **[D]** derived (calculation shown) · **[Doc]** documented (URL) · **[H]** hypothesis, untested.
**Guardrail:** nothing in this document comes from viewing dataset frames. Video facts come from container headers only.

## 1. Objective and constraints (unchanged from reframing §1, §7)

- **Output per video:**
  - binary verdict;
  - events with `type`, `timecode_sec`, `description`, and 1–3 JPEG frames;
  - an RK clause per event.
- **Operating constraints:** ≤5 min per video through the API; fully local and offline after weights load; commercially licensed open source; no faces, no audio.
- **Claim model:** a violation claim = action confidence + impropriety confidence (source: clause or organizer label) + citation. An unusual action is not a violation (reframing §4.3).
- **What a better solution demonstrably improves:**
  - no missed violation videos on similar footage;
  - a correct moment and frame;
  - a type and clause a reviewer accepts;
  - survival on the one new-angle video;
  - claims that stay within what was visible.

## 2. New facts established in this round

| # | Fact | Label | Consequence |
|---|---|---|---|
| N1 | All 42 files: H.264, **464×848, portrait** (identity track matrix), variable ~29.8–30.0 fps | [M] container headers | Low resolution; portrait framing |
| N2 | Bitrate ≈ 28.7 MB / 142.5 s ≈ 1.6 Mbit/s ≈ 0.14 bits/pixel/frame | [D] | Compression further smears fine detail |
| N3 | A ~140×70 mm banknote is ~43×22 px if the frame width covers 1.5 m at desk level, ~26×13 px at 2.5 m, ~19×9 px at 3.5 m. A palm (~9×19 cm) is ~17×35 px at 2.5 m. Frame height = 1.83 × width | [D]; the scene width is **unknown** until people look (X1) | Cash is in the small-object regime (<32 px) for any plausible width ≥2 m. Hands are borderline. **"Is it cash?" may be undecidable from pixels.** |
| N4 | Positive training signal = **~22 labelled events** (one integer second each) in 21 unique videos, not hundreds of windows | [D] from labels | Supervised learning of violation classes is few-shot at best; overfitting and shortcuts are near-certain without controls |
| N5 | The jury runs the new-angle video **automatically through the API**. Nobody can draw zones or calibrate for that camera | [D] from brief §10, FAQ 4, 13 | Anything that needs per-camera manual setup has *no* setup for exactly the video that tests robustness |
| N6 | Qwen2.5-VL: 14 px patch, 2×2 spatial merge, 2 frames per temporal patch → 1 token per 28×28 px per frame pair. 464×848 resizes to 476×840 → **~510 tokens per 2 frames**. A 145 s video takes ~37k tokens at 1 fps, ~74k at 2 fps | [Doc] [qwen-vl-utils source](https://github.com/QwenLM/Qwen2.5-VL/blob/main/qwen-vl-utils/src/qwen_vl_utils/vision_process.py), [tech report](https://arxiv.org/abs/2502.13923); [D] token count | Whole-video input fits a 128k context |
| N7 | qwen-vl-utils defaults: per-frame cap 768 tokens (~602k px), total budget 128000·28²·0.9. At 2 fps × 145 s the per-frame cap is ~622k px, so **464×848 is not downsampled by default** | [Doc] same source; [D] | Corrects our first assumption (D6): downsampling is a **VRAM choice**, not forced. A cascade's advantage is cost, plus the option of feeding crops at higher token density, not raw resolution |
| N8 | Qwen2.5-VL-7B LLM: 28 layers, 4 KV heads, head_dim 128 → KV ≈ 56 KB/token → ~2 GB at 37k tokens, ~4 GB at 74k. Weights ~5–6 GB in 4-bit | [Doc] config, via fact-check agent; [D] | 1 fps whole-video on a 12 GB GPU: plausible. 2 fps: tight. **Untested.** System RAM in WSL is only ~9 GB, which is a loading risk |
| N9 | Rule questions can share **one video prefill**: one JSON prompt covering all rules, or prefix caching. "N rules × full video" is not an inherent cost multiplier | [D] | Removes one investigator's "multi-rule exceeds budget" objection |
| N10 | Qwen2.5-VL aligns positional time to absolute time; Qwen3-VL adds text-timestamp alignment for "timestamp-grounded event localization" | [Doc] [Qwen2.5-VL report](https://arxiv.org/abs/2502.13923), [Qwen3-VL-8B card](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) | Temporal grounding is a documented design goal. **Its accuracy on fine hand actions is undocumented** |

### 2.1 Licenses (commercial use; the service is network-exposed)

| Status | Models | Source |
|---|---|---|
| **OK, verified directly** | Qwen2.5-VL-**7B** (apache-2.0); Qwen3-VL-8B (Apache 2.0); InternVL3-8B (MIT, Qwen2.5 backbone Apache 2.0) | HF model cards |
| **Not OK / trap, verified directly** | Qwen2.5-VL-**3B** (`qwen-research`, non-commercial); **YOLO-World: GPL-3.0**; **YOLOE: AGPL-3.0**; MiniCPM-V 2.6 weights need a registration form before commercial use | [3B card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct), [YOLO-World LICENSE](https://github.com/AILab-CVC/YOLO-World/blob/master/LICENSE), [YOLOE LICENSE](https://github.com/THU-MIG/yoloe/blob/main/LICENSE), [MiniCPM-V card](https://huggingface.co/openbmb/MiniCPM-V-2_6) |
| **Ultralytics YOLO and its RT-DETR port: AGPL-3.0** | Commercial use is *permitted*, but a network service must offer its full source. That's a risk for "the bank uses it commercially" (FAQ 34), not an outright ban. Avoid unless the team accepts open-sourcing | AGPL text; fact-check agent |
| **Reported Apache/MIT by the fact-check agent, not re-verified** | lyuwenyu RT-DETR, D-FINE, RF-DETR, YOLOX, RTMDet/MMDetection, RTMPose/MMPose, OWLv2, Grounding DINO, SigLIP/SigLIP2, DINOv2 (relicensed Apache 2.0), VideoMAE V2, X-CLIP (MIT), V-JEPA 2 (MIT), SmolVLM2, LLaVA-OneVision, Molmo | Re-check each one before use: **this agent got 3 of the items above wrong** |
| **Avoid or review** | DINOv3 (custom licence), original V-JEPA (CC BY-NC), Gemma 3 (custom terms) | Fact-check agent |

## 3. Research findings and provenance

Three independent investigators (one per direction), a critic and a fact-check agent ran in round 1, plus direct checks. **Evidence quality was low**: each investigator made 7–10 tool calls and cited few or no URLs. What follows keeps only what survived checking.

| Direction | Survives | Discarded as unsupported or wrong |
|---|---|---|
| Structured perception + rules | Mechanism: primitives → symbolic events → temporal predicates/FSM. Omissions as "required step not seen within W". Compute is likely small relative to 5 min [H, plausible]. Roles from position/track history/clothing, without faces | Reliability "85–90 %", "60–70 % coverage", "15–30 % cash misclassification", "95 s per video" (all invented). "Banknote 40–80 px" (assumes a 1.2 m-wide frame; see N3). "Manual zones per camera solve the new angle" (N5). "AGPL blocks commercial use" (overstated; §2.1) |
| Learned spatio-temporal | The **duration shortcut** is this family's main trap (needs leave-one-clip-out and duration-matched controls). Type/description/clause aren't native and need an extra component. A one-class "normal" model trained on one angle will flag the new angle as novel | "~840 positive windows" (N4: ~22 events). "DINOv2 non-commercial" and "X-CLIP restricted" (§2.1). "2–3 weeks of integration". The proposed experiment's "middle window per video" (it can miss the event entirely) |
| Local VLM / Video-LLM | Open-vocabulary types and descriptions; no calibration; **small-object hallucination and yes-bias are the top risk**, with no task-specific benchmark. **Overhead views are rare in VLM training data** [H], so neither the training view nor the new view is guaranteed to suit the model | "LLaVA-OneVision Apache 2.0" (not re-verified). "~80 % ceiling on did-X-happen" (unsourced). "multi-rule exceeds budget" (N9) |
| Critic | F2 is closed-set by construction and needs an explicit unknown-type path. Proposer recall must be measured separately. **The human footage pass is the single most discriminating step.** A motion-only proposer is a cheap baseline that raises the bar for VLMs | "D5 token count underestimated 2×" (it dropped the 2-frame temporal patch; N6 holds) |

## 4. Morphological map

| Dimension | Options |
|---|---|
| 1. Perception primitive | pixel motion in regions (classic CV) · detections + pose + tracks · frozen embeddings · VLM text answers |
| 2. Temporal reasoning | single frame · fixed window · explicit temporal predicates / state machine · learned sequence model · VLM multi-frame context |
| 3. Violation knowledge | supervised from labels · **human mechanism catalog from the footage (C′)** · legal rule catalog (B) · zero-shot text prompts · "normal" model (novelty) |
| 4. Scene adaptation | none · manual per-camera zones (**unavailable for the jury's new-angle video**, N5) · zones inferred from behaviour · relational predicates / VLM scene questions (no geometry) |
| 5. Search | dense over the whole video · cheap proposal → expensive verification |
| 6. Decision & evidence | score threshold · rule match + clause · VLM answer + rule match + clause, with a negative-control question |

Combinations not covered in round 1 and now added:
- Knowledge source = human catalog (dim 3) feeding *both* the checklist prompts of F3/F4 and the prototypes of F2.
- Scene adaptation by behaviour-inferred zones (dim 4).
- The motion-only proposer, raised by the critic.

## 5. Candidate families

Each family differs in mechanism: where the violation knowledge lives and how evidence is produced.

| | Family | Mechanism | Unique advantage | Main failure condition |
|---|---|---|---|---|
| **F0** | **Baseline: person/motion heuristics + 2–3 rules** | Apache-licensed person detector + background-subtraction motion. Regions inferred from where people stand. Rules taken from the human catalog. Clause per rule | Cheapest. Defines the floor every other family has to beat. Partly calibration-free | Can't see objects or hand actions; coarse types |
| **F1** | **Structured perception → temporal rule engine** | Detector + pose + tracker → events (role-in-region, hand–object contact, handover, object left, presence intervals) → temporal predicates. An omission is "step B seen without step A before it" and is anchored at B, which is visible | Explainable by construction; deterministic; type and clause attached to each rule; cheap at runtime [H] | Small objects (N3); role heuristics; zone semantics on the new angle (N5); only covers what the vocabulary can express |
| **F2** | **Frozen embeddings + few-shot prototypes** | Sliding windows → frozen encoder → similarity to prototypes of human-typed mechanisms (from X1) vs. clean windows | Learns cues nobody wrote rules for; cheap | ~22 events (N4); duration/actor shortcuts; **closed set** (no unseen types, no new angle) → **viable only as a proposer, not as the decision-maker** |
| **F3** | **Whole-video local VLM, structured checklist** | One prefill of the video at 1 fps (N6, N8). One JSON prompt: per catalog rule, yes/no + seconds + visible evidence, plus an open "other" field that can only produce *hints* | Open vocabulary; no calibration; natural-language descriptions; one code path for unseen types | Hallucination/yes-bias; fine hand actions; timestamp precision undocumented for this domain; VRAM/RAM fit (N8) |
| **F4** | **Cascade: high-recall proposer → VLM verifier on short windows → rule layer** | F0/F1 events (or F2 scores) propose ±3 s windows. The VLM answers rule-specific questions plus a negative-control question on each window, possibly with a crop at higher token density around people or hands. The rule layer maps confirmed events to type and clause | Separates recall (proposer) from precision (verifier) (TRIZ, §6). Bounded cost. Each claim carries two independent supports | Anything the proposer misses is lost; two components to integrate; still exposed to VLM hallucination on the windows it keeps |

**Rejected as primary:**
- **F5, novelty/one-class from clean clips.** On the new angle everything looks novel, so it would flag false positives across that video. It also provides no impropriety source (§4.3). At most it can generate hints.
- **Zero-shot CLIP-style text-video retrieval as detector.** Fine-grained hand/cash actions are outside documented strengths [H, no domain benchmark]. Weaker than F3, which also produces descriptions.
- **Supervised end-to-end action classifier.** N4 plus the duration shortcut. The investigator's own fail criterion is likely to trigger.

## 6. Contradictions and TRIZ resolutions

**C1. Recall ("a miss is unacceptable", unseen types) vs. precision (no unconfirmed claims, as few false positives as possible).**
- *Segmentation + intermediary (TRIZ 1, 24):* split into a proposer tuned for recall and a verifier tuned for precision (F4). New risk: proposer recall becomes the ceiling, so it must be measured on its own (HX7).
- *Local quality (TRIZ 3):* per-rule evidence requirements, e.g. "cash left" requires the object to persist for ≥N s; "extra person" requires presence in ≥K frames.
- *Prior counteraction (TRIZ 9):* a negative-control question ("what would make this legitimate / is anything hidden?") before a VLM yes is accepted. New risk: it also lowers recall. That is measurable in X2.

**C2. Rules need scene semantics (counter, cash area, cashier side) vs. no calibration for the scored new-angle video (N5).**
- *Dynamics (TRIZ 15):* infer regions from behaviour in the first seconds: where the person who handles the drawer stays, and the line between the two groups of people. New risk: inference errors are silent and need a confidence check and a fallback.
- *Mechanics substitution (TRIZ 28):* replace geometric zones with relational predicates (object between two people, a person on the far side of a detected counter edge) or with VLM scene questions ("which person is behind the counter?"). New risk: a VLM role error propagates into every rule.

## 7. Technical risks (requested list)

| # | Risk | Why | Affects | Resolved by |
|---|---|---|---|---|
| R1 | **Hands and cash not resolvable** at 464×848 | N2, N3 | F1 cash predicates, F3/F4 cash questions | X1 (humans measure px and judge "is it cash?"), X3 |
| R2 | **Single frames are not enough; order matters** | Handover, counting before handover, omissions are sequences [H] | F2 per-frame variants, single-frame VLM | X1 (frame vs. sequence column) |
| R3 | **Absence of a required action** | Not seen ≠ not done; occlusion; the omission timecode is the team's choice (FAQ 10) | All. F1 handles it formally; VLMs have known difficulty with "did NOT happen" [H] | X1 (omission share, visible anchor), X2 (negative questions) |
| R4 | **New angle: recognition and calibration** | One training view; N5 forbids manual setup | F1 (zones), F2 (embeddings); F3/F4 less affected but untested | **Own phone re-staging (E7b).** Nothing else gives evidence |
| R5 | **VLM hallucination / yes-bias**, fluent unconfirmed claims | Known general issue; no domain benchmark | F3, F4 | X2 (false yes on clean windows) |
| R6 | **Shortcuts and tiny positives** | Duration confound (70 %); ~22 events | F2, any threshold tuned on training | Leave-one-clip-out + duration-matched controls |
| R7 | **Compute / memory** | 12 GB VRAM ok on paper; ~9 GB WSL RAM is tight for loading a 7B; hosting unknown | F3 most, F4 | X2 timing; raise the WSL memory limit; E9 |
| R8 | **License traps** | YOLO-World GPL, YOLOE/Ultralytics AGPL, Qwen2.5-VL-3B non-commercial | All | §2.1; verify each dependency before use |
| R9 | **Roles without faces** | Position/clothing/track cues may be ambiguous, especially on the new angle | F0, F1, F4 | X1 (which cues humans used), X3 (track stability) |
| R10 | **Experiment hygiene** | Local VLM outputs on dataset frames **are descriptions of frames**, which §7 forbids from reaching cloud AI | X2 | Score X2 locally; share only counts with AI coding tools |

## 8. Testable hypotheses and cheapest discriminating experiments

### 8.1 Hypotheses (each with a pass/fail criterion)

| ID | Hypothesis | Test | Discriminates |
|---|---|---|---|
| HX1 | ≥80 % of labelled events can be judged by a person from the native video within ±3 s of the label using only {person/role, hand, generic hand-held object, scene region, time order} | X1 | F1/F0 viable as core or proposer vs. only F3/F4 |
| HX2 | For ≥50 % of events the decisive cue needs ≥2 s of context (order), not a single frame | X1 | Multi-frame (F1 state machine, F3/F4 windows) vs. frame-level anything |
| HX3 | In cash-related events, people can identify the object as cash at native resolution in ≥80 % of cases, **and** an open-vocabulary detector (OWLv2 / Grounding DINO) finds it in ≥60 % with ≤1 false detection per clean window | X1 + X3 | Whether "cash" may appear in rules at all, or only as "hand-held object" |
| HX4 | An Apache-licensed local VLM (Qwen2.5-VL-7B-AWQ or Qwen3-VL-8B/4B), given a ±3 s native window, states the event's mechanism correctly in ≥7/10 labelled windows **and** answers "yes" to a violation checklist item in ≤1/10 matched clean windows | X2 | F3/F4 viable vs. VLM only as a frame describer |
| HX5 | The same VLM's timestamps fall within ±2 s of the label in ≥7/10 windows | X2 | VLM can localize vs. localization must come from F1/F0 |
| HX6 | An Apache-licensed detector + tracker keeps people with ≤1 ID switch per 6 s window in ≥9/10 windows | X3 | Role tracking (F1/F4 proposer) feasible |
| HX7 | A person/motion-event proposer with ≤10 candidate windows per video contains the labelled second in ≥20 of 22 events | X3 (offline from its outputs) | F4 feasible (proposer recall) |
| HX8 | Each omission event has a visible subsequent step it can be anchored to | X1 | Omission rule form "B without A" vs. window-end anchoring |
| HX9 | Recognition transfers to another angle | E7b (own phone re-staging) | **Untestable on the dataset.** Report untested if not done |

### 8.2 The three minimal experiments

**X1. Structured human footage pass (no code; ~1–1.5 h wall-clock for 4 people). Run first.**
Extends reframing E2–E5. Per labelled event and per clean clip, fill one row:
- mechanism, written without scene-specific words (reframing §4.2 test);
- primitives needed (person/role, hand, object and its kind, region);
- frame or sequence;
- key object size in px, measured with any local image viewer;
- "is it recognizably cash?";
- omission or commission, and the visible anchor for omissions;
- label offset (onset, peak or completion);
- cues used for roles;
- "would a person entering or leaving, or hands moving near the counter, have flagged this second?". This is a paper estimate of proposer recall.

Also resolve Х-4/Х-47 (two moments, one file).
Pass/fail: HX1, HX2, HX3 (human part), HX8 directly. This decides which primitives any rule may rely on, and produces the checklist for X2.

**X2. Local VLM probe (~2 h incl. install + download; needs X1's mechanism list for the checklist arm).**
- Model: Qwen2.5-VL-7B-Instruct-AWQ or Qwen3-VL-8B/4B, all Apache. Not the 3B.
- Data: 10 labelled windows (label ±3 s) + 10 duration-matched clean windows at random times, shuffled and blind.
- Arm A: open description ("what do the people's hands do, in order; say 'unclear' when unsure").
- Arm B: checklist JSON (per rule: yes/no, seconds, visible evidence) + a negative-control question.
- Also run three whole clips at 1 fps to measure prefill time, VRAM, and timestamp behaviour on full input.
- **Scoring:** done locally by people against the X1 sheet; only counts leave the machine (R10).
- **Pass:** HX4 and HX5, plus ≤30 s per window and the whole-clip run finishes within ≤2 min for a 145 s clip.
- **Fail:** VLMs drop out as detectors. At most they stay as a describer for evidence frames.

**X3. Perception + proposer probe (~1.5 h; can run in parallel with X2).**
- Models: Apache-licensed detector (lyuwenyu RT-DETR via HF transformers, or D-FINE / RF-DETR; licenses re-verified) + RTMPose + OWLv2 on the same 20 windows at 5 fps, plus every full clip for the proposer.
- Measure: person ID switches; hand keypoint presence when people see hands; OWLv2 "banknote / cash / money" recall against the cash instances people marked; false detections in clean windows.
- Proposer: run a simple rule (person enters or leaves a region inferred from track density; hand motion peaks) and measure the label second's hit rate at ≤10 candidates per video.
- **Pass:** HX3 (detector part), HX6, HX7.

**Not in the minimal set, but still cheap:**
- E1 (one message to the organizers about type judging and multi-event scoring).
- E7b (phone re-staging from another angle). **The only evidence on robustness.**
- An F2 embedding probe with corrected design: label windows vs. matched clean windows, leave-one-clip-out, a duration-only baseline. Worth running only if F2 becomes a proposer candidate.

## 9. Finalists, baseline, and what would change the ranking

**No architecture is chosen here.** Current standing:

| Rank (provisional) | Family | Why it's here | Promoted if | Demoted if |
|---|---|---|---|---|
| 1 | **F4 cascade** | Best structural answer to C1; calibration needs depend on the proposer | HX4 + HX7 pass | HX7 fails (proposer misses events) → F3; HX4 fails → F1 |
| 2 | **F3 whole-video VLM** | Simplest path to open-vocabulary types and descriptions; no calibration | HX4 + HX5 pass **and** whole-clip timing fits; or HX7 fails | HX4 fails, especially false yes on clean windows; or the VRAM/RAM fit fails |
| 3 | **F1 structured rules** | Deterministic and explainable; cheapest runtime | HX1 + HX6 pass and HX4 fails | HX1 fails (events need cues outside the vocabulary) or region inference can't work without calibration (N5) |
| floor | **F0 baseline** | Must be beaten by any finalist on training data with leave-one-clip-out | — | — |

**Conditions that change everything:**
- If X1 shows that people *can't* judge most events at native resolution, nothing visual will. The catalog then shrinks to what is perceivable, and that limit is declared.
- If E1 reveals a fixed type list with exact matching, the naming effort shifts toward the organizers' names (reframing §6.2).
- If E7b shows key cues vanish from another angle, robustness claims are limited to the cues that survived, whichever family wins.

**Recommended next step:** X1 now (all 4 people, about 1 h). In parallel, one person installs the local stack (torch, transformers, the VLM and detector weights) so that X2 and X3 can start the moment X1's mechanism list exists. Send E1 to the organizers today.

## 10. Remaining unknowns

- Scene width (N3) and so every pixel bound.
- Real VLM timing and memory on this laptop (N8 is derived).
- How well VLMs ground hand actions in time.
- Licenses of the not-re-verified models (§2.1).
- Type-judging method and test balance (E1).
- Recognition transfer to another angle (HX9).
- Hosting (E9).
