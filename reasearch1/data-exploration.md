# Data-Centric Exploration — Datathon 26 (ForteBank)

Inputs: `task.md`, `problem-reframing.md` (rev 5), `problem-exploration.md` (X1–X3), `technology-research-landscape.md`, `data/open/open_labels.xlsx`, `.mov` container headers. This is decision support for the data side. **It does not choose a model or architecture.**

**Evidence labels:** **[M]** measured here (script in §A.6) · **[D]** derived, calculation shown · **[Doc]** documented at a cited URL I or a research agent opened · **[H]** hypothesis, untested · **[P]** pending the human footage pass (X1).
**Guardrail:** no frame was decoded or viewed. Every dataset fact comes from the labels file and the MP4/MOV atom headers (`moov/mvhd`, `tkhd`, `mdhd`, `stsz`). No violation type below is inferred from filenames or timestamps.

---

## 0. Short answer

**Raw example count is not our bottleneck.** It would only bind if we trained a violation classifier, and the exploration has already demoted that (exploration §5). The binding data problems, in order:

1. **Annotation granularity [M].** 22 integer-second points with no type, no onset/offset, no roles, no objects. Without these we can't score localization, type, or proposer recall properly. **Cheapest fix with the largest payoff: extend X1's sheet by ~10 columns (§I).**
2. **Zero evidence on another viewpoint [M].** All 40 unique clips share one camera. Image augmentation can't stand in for a new viewpoint (§D.A). **Only a small, self-recorded other-angle set gives any evidence (§D.B).**
3. **Unknown hard-negative coverage [P].** If the clean clips contain no look-alike actions, we can't measure false positives on clean test videos. One false event flips a clean verdict. **Matched legal/prohibited pairs recorded in the same session as item 2 fix this.**
4. **Pixel scale of cash and hands [D].** This is physics, and more footage doesn't change it. Crops, token density and sampling (X2/X3) do.
5. **Normative ambiguity and unseen types.** No dataset fixes these. The rule catalog does (reframing §5, B).

Public datasets: **no public bank-teller or cashier-compliance video dataset was found** (§C). Nothing public is worth downloading before X1–X3 report. Generative video and simulation: **avoid** (§D).

---

## 1. Bottleneck diagnosis: what data can and can't fix

| Candidate bottleneck | Evidence now | Can more data fix it? | What fixes it instead / as well |
|---|---|---|---|
| Insufficient examples | ~22 labelled events in 21 unique violation videos [M] | Only for training strategies we're not pursuing. For zero-shot/rule approaches, extra examples serve **evaluation**, not learning | Strategy A/B (§8) |
| Missing violation categories | Guaranteed by FAQ 9; the training categories are undisclosed (FAQ 8) | Partly: staging visible-but-unstaged rules (B \ C′) gives **evaluation** coverage. No dataset contains the jury's unseen types | Rule catalog from RK acts (reframing E6/E8) |
| Missing fine-grained annotation | No type, onset/offset, roles, objects, scenario IDs [M] | **Yes. Annotation, not video** | X1 schema extension (§I) |
| Low resolution | 464×848, ~1.6 Mbit/s [M]; a banknote is roughly 19–43 px wide depending on scene width [D, exploration N3] | No. Recording at higher resolution would create a domain gap with the test footage | Crops at higher token density, detector input size, measured in X3 and DX3 |
| Camera-angle variation | One view in training [M]; the test has a new one (FAQ 4) | **Yes, for evaluation**: own footage from other angles is the only evidence. For training: too little, too late, too different | Viewpoint-independent rule definitions (reframing §4.2) |
| Lack of hard negatives | Unknown [P] | **Yes**, cheaply, by re-staging matched pairs | Negative-control questions; per-rule evidence requirements (exploration C1) |
| Temporal ambiguity | 1 s labels; convention (onset/peak/completion) unknown; X-4/X-47 disagree [M] | No. Better **annotation** of the existing clips fixes it | X1 onset/peak/offset columns; tolerance curves (§E) |
| Hands/objects under-represented | Unknown how often hands are occluded [P] | Only if we fine-tune a detector, which needs licence-clean, domain-matched boxes | Zero-shot detectors first (X3); then decide |
| Normative ambiguity | Clauses not yet verified (reframing E6) | No | Legal research + human verification |
| Domain shift to test | Test is "similar" (FAQ 4) except one new-angle video | Own footage only approximates it: a different room, desk, actors and props | Report cross-view results as indicative, not as a prediction |

---

## A. Dataset audit

### A.1 Verified facts [M]

| Fact | Value |
|---|---|
| Files / label rows | 42 / 42, matched one-to-one. Prefix `X-` (Latin) for 1–2, `Х-` (Cyrillic) for the rest |
| Byte-identical duplicates (md5) | **Х-4 ≡ Х-47** (labels: violation at **57 s** and at **68 s**); **Х-5 ≡ Х-48** (both clean, consistent) |
| Unique videos | **40**: 21 violation, 19 clean |
| Label rows with a time | 22 (21 unique videos; Х-4 carries two times) |
| Label format | One integer second per row ("22 секунда", "1минута 8 секунда"). No type, no interval, no role or object |
| Codec / geometry | All 42: one video track, H.264 (`avc1`), stored 464×848, identity matrix → **portrait** |
| Frame rate | Frames ÷ track duration = 29.76–30.00 fps; variable frame rate likely (phone-style) |
| Bitrate | 1.61–1.67 Mbit/s for every clip, near-constant: a CBR-like encoder |
| Duration | 11.6–142.5 s; total unique footage **21.66 min** |
| Violation clips | duration median 20.4 s (11.6–72.7), total 544.5 s; 10 of 21 are ≤20 s, 3 are >30 s |
| Clean clips | duration median 26.4 s (15.6–142.5), total 755.4 s; 5 of 19 are ≤20 s, 9 are >30 s |
| Label times | 5–68 s, median 13.5 s; 17 of 22 at ≤20 s |
| Label position ÷ duration | 0.23–0.94; time remaining after the label: 2.6–26 s (median ≈ 7.6 s) |
| Numbering gaps | 6, 7, 9, 36, 41, 42 missing (purpose unknown) |

### A.2 Shortcut correlations (derived from the numbers above) [D]

| Shortcut | Size | Consequence |
|---|---|---|
| **Duration → verdict** | In-sample best threshold (≤25.9 s → violation): 28/40 = 70 %. **Leave-one-out** (threshold re-fitted on 39, tested on 1): **25/40 = 62.5 %**. Majority class: 52.5 % | Any learned or tuned component can pick up clip length. Every verdict experiment must beat **62.5 % LOO** |
| **Bitrate → verdict** | 28/40 in-sample, but bitrate correlates with duration (Pearson r = −0.65 against log-duration). Mostly duration in disguise | Re-encoding all clips to the same settings removes it for any model that sees compression artefacts |
| **Relative position → timecode** | Predicting `t = median(label/duration of other videos) × duration`, without looking at a single pixel, lands within **±1 s in 4/22, ±2 s in 9/22, ±3 s in 12/22, ±5 s in 18/22** events (leave-one-video-out) | Clips appear trimmed around the event. **Localization claims must beat this blind baseline.** HX5's "±2 s in ≥7/10" is only ~1.7× the blind rate |
| Actors, clothing, number of people, lighting, props | Not measured | [P] X1 columns |

### A.3 Annotation reliability

| Issue | Status |
|---|---|
| Х-4/Х-47: same bytes, two different times (57 s, 68 s) | Either **two events** in one video, each row labelling one, or label noise of ~11 s. [P] reframing E4b. Until resolved: treat Х-4 as one video with **two candidate events**, and exclude it from localization scoring if X1 can't confirm both |
| Label convention ("Nth second" = N.0 or [N−1, N)? onset, peak or completion?) | Unknown. Score both N.0 and N+0.5 and report the difference (§E) |
| Number of events per violation video | 1 label per row; whether other videos also contain more than one event is unknown [P] |
| Clean = "no violation anywhere in the clip"? | Assumed, unverified [P]. A person should note anything suspicious in clean clips (§I) |
| Omission events: where the timestamp sits | Unknown (FAQ 10 leaves it to the team; the labellers chose *something*) [P] |

### A.4 Missing information

| Unknown | Who/what resolves it |
|---|---|
| Violation mechanisms, how many there are, recurrence per mechanism | X1 (humans) |
| Near-duplicates: the same scenario re-shot with small changes | X1 "scenario ID" column. Optionally a local perceptual-hash script run by a teammate; output stays local |
| Actor/costume reuse across classes | X1 |
| Hard negatives in clean clips | X1 |
| Scene width → real pixel size of cash/hands | X1 (pixel measurements) |
| Test class balance, how types and multi-event videos are scored | E1 (organizers) |

### A.5 Known vs. not investigated

- **Known [M]:** composition, duplicates, durations, label times, geometry, bitrate, the duration and position shortcuts.
- **Not investigated (by design, guardrail):** anything visual. That covers mechanisms, actors, occlusion, objects, roles, hard negatives and near-duplicates. They belong to the team's video analyst and X1, and this document does not duplicate that work.

### A.6 Reproduction

Scripts are in `validation-evidence/data-audit/`. They use the stdlib only and read only the xlsx XML and the MOV atom headers; no frame is decoded.

```
python3 -I validation-evidence/data-audit/meta.py data/open > /tmp/meta.txt
python3 -I validation-evidence/data-audit/stats.py /tmp/meta.txt       # §A.1 composition, durations, label positions
python3 -I validation-evidence/data-audit/baselines.py /tmp/meta.txt   # §A.2 LOO duration verdict, timecode prior
```

---

## B. Data gap matrix

**All mechanism rows are provisional [H].** They come from the brief's scope (§1, §6: cash operations, encashment, cash-room organisation and security) and the roles in FAQ 3. **They do not come from the footage.** Column "Coverage in training data" stays **[P]** until X1 maps each labelled event to a row, or adds a new row. Rows X1 doesn't confirm become candidate **unseen types** (B \ C′) and are worth staging for evaluation only if a clause supports them.

### B.1 Requirements per provisional mechanism

| # | Provisional mechanism | Decisive visual evidence | Frame or sequence | Objects / interactions to recognise | Temporal context needed | Omission observable? | Invisible facts (§7 limit) | Legitimate look-alikes | From another viewpoint |
|---|---|---|---|---|---|---|---|---|---|
| M1 | Valuables (cash, bags, keys) left exposed or accessible while the responsible person is absent or turned away | Object visible in an open area + responsible person absent/away for a duration | Sequence (persistence ≥ N s) | Cash/bag/drawer state; person presence | Several seconds to tens of seconds | It's a *state*, so yes, if the object stays visible | Whether a colleague nearby is responsible; whether it's within the rules' allowed time | Cash being actively counted; a brief turn to a printer; a drawer about to be closed | The object may be occluded by the counter edge; "absent" may mean off-frame |
| M2 | Unauthorised person in the cashier/cash area | A person crosses into the restricted side or stays there | Sequence (entry + dwell) | Person, track, zone boundary; role cue without faces | Entry to exit | n/a (commission) | Authorisation, identity (faces banned, FAQ 29) | A second cashier, supervisor or collector who *is* authorised | Zone boundary must be re-inferred; occlusion of the counter line |
| M3 | Cash handed over outside the prescribed path (bypassing the tray/window, handed to the wrong role, passed behind the counter) | Hand-to-hand transfer between two roles, or object crossing the boundary | Sequence (grasp → move → release) | Two hands, small object, roles | 1–3 s | n/a | Whether that path is allowed for this operation | Passing a document, receipt or pen; returning ID | Hands overlap from oblique views; depth makes "across the counter" ambiguous |
| M4 | Required count or check skipped before handover (count in view of the client, check the banknotes) | Handover **without** a preceding counting/inspection segment | Sequence, order-dependent | Cash, counting hand motion or counting machine | The whole operation (10–60 s) | **Partly**: anchor at the visible handover ("B without A before it", exploration F1) | Counting done off-camera or by machine; operation type | Machine counting; small amounts; a re-count already seen earlier | Counting gestures shrink or vanish at oblique or rear angles |
| M5 | Encashment/collector procedure irregularity (bag handover without visible checks, the collector unaccompanied in the cash area, door left open) | Bag/case transfer + presence/sequence of other roles | Sequence | Collector role cue (uniform), bag, door/zone | Whole visit | Partly | Documents, seals, authorisation, schedules: **mostly invisible** | Routine authorised collection | Uniform cue may survive; bag details won't |
| M6 | Cashier leaves the workstation without securing cash or the drawer | Person leaves + cash/drawer still open | Sequence | Person exit, drawer/cash state | Departure ± a few seconds | Yes, if the state is visible at departure | Whether another cashier took over | Short step back within reach | Exit direction and drawer visibility change |
| M7 | Client document/ID check skipped before an operation | No document handling before cash handover | Sequence, order | Document vs cash vs receipt (small, flat, similar) | Whole operation | Weak: "no document seen" ≠ "no check" | Whether a check is required (amount thresholds, repeat client) | ID checked earlier off-frame; document on the counter | Very weak: flat small objects at a low pixel count |

### B.2 Data need per mechanism

| # | Coverage in training data | Most useful extra positives | Most useful extra negatives (hard) | Annotation vs. more video | Main limit that data can't remove |
|---|---|---|---|---|---|
| M1 | [P] | Same act, other angle, different object (bag vs cash) | Cash exposed **during** legitimate counting; drawer briefly open | Onset of "unattended" + duration matter more than more clips | Off-frame ≠ absent |
| M2 | [P] | Entry from the other side, partial entry (leaning over) | An authorised colleague entering (distinct clothing); reaching over the counter without entering | Track/zone annotation is cheap and high value | Authorisation is invisible; roles without faces |
| M3 | [P] | Different objects and speeds; partial occlusion | Same gesture with a document or receipt; handover via the tray | Need onset/offset of the transfer (±0.5 s) | Cash vs paper at ~20–40 px |
| M4 | [P] | Fast counting; counting machine present but unused | Count done, then handover (the matched pair) | **Order annotation** (step A at t1, step B at t2) is the key | "Not seen" ≠ "not done" |
| M5 | [P] | Hard to stage credibly without uniforms or bags | Routine collection with all visible steps | Role annotation | Most preconditions are invisible; declare as a limit |
| M6 | [P] | Exits in different directions | Step away within reach; colleague takes over | Exit time + state at exit | Takeover arrangements are invisible |
| M7 | [P] | — | ID shown on the counter | Low priority | Weak observability; likely declare out of scope |

**Prediction to check in X1:** mechanisms whose decisive cue is *relational and large-scale* (M1, M2, M6: people, presence, dwell) will be both more frequent and more robust to viewpoint than those that hinge on *small-object identity* (M3, M4, M7). If X1 confirms this, the data budget should go to hard negatives and other-angle footage for M1/M2/M6-type rules first, and to object-scale evidence (crops, DX3) for M3/M4 second.

---

## C. Public dataset inventory

**Provenance.** Four research agents searched in parallel: retail/cashier/handover, procedural/mistake, surveillance/multi-view/anomaly, and synthetic/augmentation. I re-opened the primary page for every licence that would change a recommendation. Marks in the table: **✔ verified** (I opened the source); **agent-read** (an agent quoted it, I didn't re-open it); **✘ unverified**.

**Agent claims I checked and corrected:**
- PoseLift's "arXiv licence = commercial-friendly" was wrong; the arXiv licence covers the paper. The repo says Apache-2.0, and the data is **pose keypoints only**.
- Breakfast is **not** "CC BY 4.0": the official page states no licence.
- CaptainCook4D is Apache 2.0, not CC BY.
- DexYCB "GPL-3.0" is the toolkit's licence, not the data's.
- "Overhead view is provably optimal" and the "11–16 % side-view drop" figures weren't supported by anything I could verify. Both were dropped.

**Negative result (important):** none of the retail agent's queries found a public bank-teller, cashier-procedure or POS-compliance video dataset: "bank teller cashier activity dataset video surveillance", "self-checkout sweethearting fraud detection video", "point-of-sale dataset retail checkout video". They found patents and stock footage only.

### C.1 Inventory

| # | Dataset (URL) | Task · modality · view | Size (as stated) | Annotations | Licence (status) | Similar / different vs. ours | Class | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | [RetailAction](https://huggingface.co/datasets/standard-cognition/RetailAction) (Standard AI; ICCV 2025 workshop) | Hand–product interaction · video · **ceiling top-view, ~2.5 m**, multi-view | 42k clips (21k dual-view groups), ~41 h, 28.1 GB; 2880² captured, 600² @ 6 fps exported; 1.5–10.3 s clips | Temporal boundaries, 2D contact point, take/put/touch, body pose | "Standard AI custom license" (✔ the statement; terms ✘ not read) | **Closest viewpoint and hand scale.** Retail shelf, not a counter; no procedures; 6 fps | Transferable primitives / robustness eval, **if** the licence allows | Low–Med |
| 2 | [MERL Shopping](https://merl.com/research/downloads/MERL_Shopping_Dataset) | Action detection · video · **fixed overhead** | 106 videos × ~2 min | 5 actions (reach, retract, hand-in-shelf, inspect ×2), temporal | Commercial reproduction needs a MERL licence (agent-read) | Overhead hands, temporal localization; shelf, not counter | Research reference | Med |
| 3 | [MEVA](https://registry.opendata.aws/mevadata/) | Activity detection · video (+UAV) · 29 fixed cameras, overlapping views | ~328 h (516 GB) + 4.6 h UAV; ~184 h annotated | Activity tracks (scripted + unscripted, ~100 actors) | **CC BY 4.0** ✔ ([licence](http://mevadata.org/resources/MEVA-data-license.txt)) | Real multi-view surveillance; person-scale activities (agent: incl. object transfer, entering); campus scenes, no cash | Robustness eval (person-level, M2-type) | **High** (size) |
| 4 | [Cornell bimanual handover](https://zenodo.org/record/7767535) | Human–human handover · RGB-D + mocap · lab | 240 bimanual + 120 unimanual recordings; 8.9 GB compressed | **Phases: reach / transfer / retreat** | **CC BY 4.0** ✔ | Handover mechanics; lab, 10 objects, not cash | Transferable primitive: **use the phase definitions as our onset/offset convention**, not the data | Low (concept only) |
| 5 | [HOH handover](https://hohdataset.github.io/) | Handover · RGB-D, multi-view | 2,720 interactions | Grasp, phases, segmentation | CC BY-NC-SA 4.0 (agent-read) | As 4, but NC | Research reference | — |
| 6 | [PoseLift](https://github.com/TeCSAR-UNCC/PoseLift) | Shoplifting · **pose keypoints only, no video** · 6 indoor retail CCTV cameras | 155 videos (agent) | Person ID, box, keypoints | Apache-2.0 ✔ | Anonymised pose is a nice idea; shoplifting ≠ procedure; no pixels | Research reference | Low |
| 7 | [CaptainCook4D](https://github.com/CaptainCook4D) | Procedural **error** recognition · egocentric video | 384 recordings, 94.5 h | Steps, errors, descriptions | Apache 2.0 ✔ | Error taxonomy; egocentric cooking | Research reference | High |
| 8 | [IndustReal](https://github.com/TimSchoonbeek/IndustReal) ([data](https://data.4tu.nl/datasets/b008dd74-020d-4ea4-a8ba-7bb60769d224)) | Procedure step recognition **with execution errors and omissions** · egocentric (HoloLens 2, 10 fps) | ~77 GB | Steps, errors, assembly states | Apache-2.0 ✔ (code and 4TU page) | Omission handling; egocentric toy assembly | Research reference | High |
| 9 | [EgoOops](https://github.com/Y-Haneji/EgoOops-annotations) | Mistake detection **referring to procedural text** · egocentric | 50 videos (agent) | Video–text alignment, mistake types | CC BY-SA 4.0 ✔ | Mirrors our "rule text + video" setup; egocentric | Research reference | High |
| 10 | [EgoPER](https://www.khoury.northeastern.edu/home/eelhami/egoper.htm) | Procedural error detection · egocentric | 28 h (agent) | Error types: omission, addition, modification, slip, correction | ✘ unverified | **Error taxonomy reusable** for our mechanism sheet | Research reference | — |
| 11 | [Assembly101](https://arxiv.org/abs/2203.14712) | Procedural activity + **mistake detection** · 8 static + 4 egocentric views | 4,321 videos, 513 h (agent) | Coarse/fine actions, mistakes, hand poses | CC BY-NC 4.0 (agent-read) | Static multi-view of hand procedures; NC | Research reference | — |
| 12 | [NTU RGB+D 120](https://rose1.ntu.edu.sg/dataset/actionRecognition/) | Multi-view action recognition | 114k+ samples (agent) | Actions, skeletons | "**academic research only** … commercial usage … illegal" ✔ | Defines the standard cross-view protocol; living-room actions | Not worth using (licence); protocol reference only | — |
| 13 | EPIC-KITCHENS-100, Something-Something v2 | Fine-grained hand actions · egocentric / crowd-sourced | Large | Verb–noun / template labels | CC BY-NC 4.0; research-only DLA (agent-read) | Fine hand actions; NC | Not worth using | — |
| 14 | [Breakfast](https://serre.lab.brown.edu/breakfast-actions-dataset.html) | Temporal segmentation · 3–5 uncalibrated cameras per kitchen | 1,712 videos (agent) | Coarse/fine segments | **No licence stated** ✔ | Third-person procedures; cooking | Not worth using | — |
| 15 | UCF-Crime, XD-Violence, ShanghaiTech, CUHK Avenue, UBnormal, NWPU | Video anomaly detection | Various | Video- or frame-level "abnormal" | Research/academic-only or unverified (agent-read) | Labels crimes, violence and unusual motion. **A procedural violation can look perfectly normal, so the "anomaly" label doesn't carry our meaning** | **Not worth using** | — |
| 16 | Banknote image sets ([BankNote-Net](https://arxiv.org/abs/2204.03738), Roboflow sets) | Currency recognition/detection · close-up images | ~25k (BankNote-Net, agent) | Boxes/classes | ✘ unverified / per-dataset | Close-up flat notes ≠ 20–40 px notes in a hand from 2+ m | Conditional only (§H), behind locally boxed frames | Med |
| 17 | ActivityNet, THUMOS14, FineAction, Toyota Smarthome, PKU-MMD, VIRAT, Okutama | Generic localization / multi-view / aerial | Large | Segments | Mixed, mostly NC or unverified | Benchmarks, not our domain | Research reference / not worth using | — |

### C.2 Research findings relevant to data strategy

- **Zero-shot VLMs on procedural mistakes.** A single pretrained video-language model, with no task-specific training, matched or beat supervised baselines for procedural mistake detection on EgoPER and CaptainCook4D ([ZeProM, arXiv 2606.21579](https://arxiv.org/abs/2606.21579), abstract ✔). Caveat: egocentric cooking, not overhead cash. It's still the best available evidence that strategy A (§8) isn't hopeless for "skipped step" mechanisms.
- **Mistake detection remains hard in general**: telling allowed variation from error needs context ([review, arXiv 2510.19292](https://arxiv.org/abs/2510.19292), agent-read). This supports investing in hard negatives (D.E).
- **One-class mistake detection** trained only on correct sequences ([PREGO, CVPR 2024](https://arxiv.org/abs/2404.01933), agent-read). Interesting for unseen types, but it inherits the new-angle novelty problem (exploration F5). Reference only.
- **Synthetic multi-view humans help new viewpoints** for full-body actions ([SURREACT](https://arxiv.org/abs/1912.04070), abstract ✔). That doesn't carry over to hand-scale procedures in 24 h (§D.C).

### C.3 Download decision

**Nothing is worth downloading now.** For each candidate, the hypothesis that would justify it:
- **RetailAction:** only if (a) its licence permits our use, read word for word, **and** (b) X3 shows a hand–object contact detector failing on overhead views in a way that more overhead hand data might fix. Our own re-staged footage tests (b) more directly.
- **MEVA:** only if an M2-type (person entering a zone) detector fails on own other-angle footage and we need more viewpoints of person-level events. At 516 GB, pull a single site or camera subset, never the whole set.
- **Banknote images:** only behind the §8 gate, and after locally boxed organizer frames have been tried.
- **Everything else:** use as a concept reference (EgoPER's error taxonomy; Cornell's handover phases), or not at all.

---

## D. Synthetic data strategy comparison

### D.0 Summary

| Strategy | Realism vs. test | Label control | Temporal consistency | Effort (24 h) | Domain gap | Licence/legal | Verdict |
|---|---|---|---|---|---|---|---|
| A. Conventional augmentation | Same footage | Exact, but some transforms erase the evidence | Preserved | Low | None new | None | **Only for a trained component (strategy C), and only label-safe transforms (D.A)** |
| B. Controlled re-staging | Real people, real hands, real paper; different room | Good, if a second person verifies every take | Real | **~2 h for 2 people** | Room/desk/actors differ | Own footage; consent | **Do it, for evaluation (DX1, DX2)** |
| C. Simulation / composition | Low for hands and small paper objects | Exact in principle | Exact | Days | Large | Varies (D.C) | **Avoid** |
| D. Generative video | Unreliable for hands and small objects | **Weak**: prompts don't guarantee step order | Known weakness | High; GPU time | Unknown, artefacts | Model-dependent | **Avoid** |
| E. Counterfactual / hard-negative pairs | As B | Best: only the decisive act differs | Real | In B's session | As B | As B | **Do it, inside B** |

### D.A Conventional augmentations: which preserve the label

| Transform | Preserves the label? | Risk to decisive evidence | Use |
|---|---|---|---|
| Brightness, contrast, gamma, mild colour jitter | Yes | Low | Safe for training; also a cheap robustness check |
| H.264 re-encode, mild | Yes | Low | **Re-encode every clip with one setting**: kills the bitrate cue (§A.2) |
| Strong compression, 0.5× downscale | **Not always** | Cash at ~20–40 px [D] can vanish; presence/dwell cues (M1/M2/M6) likely survive [H] | DX3 decides. Until then, not a training augmentation for object-dependent rules |
| Gaussian noise, mild blur | Mostly | Blur hits small objects first | Mild only |
| Random crop / scale | **No, in general** | A crop can cut off the entry edge (M2), the counter line (M3), or the object | Only crops that keep the whole desk area and every person |
| Horizontal flip | Relational rules: yes. Side/zone rules: **no** | Swaps the "client side" and "cashier side" | Only if every rule is relational |
| Small rotation / homography warp | Yes | No occlusion change | Mimics a slightly moved camera on a planar desk. **Not a new viewpoint** (§11, item 4) |
| Frame dropping, temporal subsampling | Only if the event lasts ≥2 sample intervals | Drops brief handovers | DX4 sets the safe rate |
| Camera shake | Yes | — | Low value: surveillance cameras are fixed |
| **Temporal crop / padding to equalise durations** | Clean sub-clip of a clean clip: yes (if "clean" holds for the whole clip, [P]). Violation: only with the event and margins inside | Cutting the event out | **Breaks the duration and position shortcuts.** Needs X1 onset/offset |

Reported evidence (from a research agent's reading, **not re-read by me**):
- A large robustness study of video action recognition under 90 perturbations, including compression and temporal ones, found transformer models more robust than CNNs: [Schiappa et al., CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/html/Schiappa_A_Large-Scale_Robustness_Analysis_of_Video_Action_Recognition_Models_CVPR_2023_paper.html).
- Video-language models are reported fragile to human-perceivable corruptions: [arXiv 2511.19032](https://arxiv.org/pdf/2511.19032).

These support running DX3 rather than assuming robustness. No source found shows that 2D augmentation substitutes for a real viewpoint change.

### D.B Controlled re-staging (recommended, ~2 h, 2–3 people)

**Purpose: evaluation only** (DX1 hard negatives, DX2 viewpoint), not training data.

- **Two phones recording simultaneously**: A as close to the organizers' overhead view as possible; B at another angle, e.g. 30–45° oblique from a front corner at ~2 m. Simultaneous capture makes the viewpoint the only variable (DX2).
- **Match the container afterwards:** portrait, scale to 464×848, H.264 at ~1.6 Mbit/s, ~30 fps, strip audio. Use local ffmpeg.
- **Set:** table = counter; a box or board = window/divider; a box = cash drawer; tray; bag (M5); ID-sized card (M7).
  - **Cash props:** real low-denomination notes owned by the team, or plain paper cut to banknote size. **Don't print banknote replicas.**
- **Actors:** team members only, with consent. Each role played by ≥2 people, with clothing swapped between takes, so actor ≠ label.
- **Shot list: 8–12 matched pairs** (violation + legal look-alike, same actors, same length, same start), from §B's rows that X1 confirms. Before X1 reports, use the generic M1/M2/M3 pairs:
  - M1: cash left on the counter while the cashier walks away ↔ the cashier steps away *after* putting the cash in the drawer.
  - M2: a "client" walks behind the counter ↔ a "colleague" in a distinct outfit does the same. **Document that the role cue is visible.**
  - M3: cash passed hand-to-hand across the counter ↔ a document passed the same way; cash placed in the tray.
  - M4: handover without counting ↔ counting shown, then handover.
  - Plus 1–2 visible-but-unstaged clause candidates (B \ C′) if E6 supports them, and 2 clips of plain normal operation.
- **Break the shortcuts:** vary clip length (15–40 s) and event position (early/middle/late) independently of the label.
- **Labels:** the shot log is written *before* each take (intended act, intended window). A second person reviews each take and records the actual onset/offset; deviating takes are relabelled or dropped. A take-ID card is shown before the action and trimmed off afterwards.
- **Volume:** 16–24 takes × 2 views ≈ 10–15 min of footage per view. ~1.5 h of recording with resets, ~30 min trim and label.
- **Normative rule:** stage a violation only if its mechanism has a clause (reframing source i) or an organizer-labelled analogue (source ii). Otherwise it's a "hard negative / unusual action" clip, not a positive.
- **Privacy rule:** own footage isn't organizer data. Still, keep it local. Shot scripts derived from X1's per-clip notes describe organizer frames, so they don't go to cloud tools either (§H).

### D.C Simulation and compositional synthesis

- [Kubric](https://github.com/google-research/kubric) (Apache 2.0, agent-read): rigid-body scenes, no documented articulated human hands.
- BlenderProc is GPL-3.0 per [its repository](https://github.com/DLR-RM/BlenderProc) (agent-read).
- Omniverse Replicator terms were reported but not verified.
- **Effort:** an animated person whose fingers grasp, count and pass a 20–40 px banknote plausibly, with a counter, drawer and second person, is days of 3D work.
- **Domain gap:** large (render vs. phone H.264).
- **Strongest positive evidence:** synthetic *whole-body* humans rendered from many viewpoints "substantially improve" action recognition at new viewpoints on NTU RGB+D and UESTC ([Varol et al., SURREACT, arXiv 1912.04070](https://arxiv.org/abs/1912.04070), abstract read). That's full-body action classes, a pipeline built over months, and supervised training. It's none of our conditions.
- **Verdict: avoid.**

### D.D Generative video synthesis

- **Licence and cost.** [Wan2.2-TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) is Apache 2.0. Its card says it needs "at least 24GB VRAM (e.g, RTX 4090)" and makes a 5 s 720p clip "in under 9 minutes" on one consumer GPU (verified). On a ~12 GB GPU it would need offloading or quantisation, so it would be slower [H]. Other generators carry restrictive terms (HunyuanVideo's community licence has territorial exclusions, agent-read; LTX-Video has revenue-tiered terms, agent-reported).
- **Hands and small objects.** Consistent hand–object interaction is still an active research problem ([GenHOI, CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Huang_GenHOI_Towards_Object-Consistent_Hand-Object_Interaction_with_Temporally_Balanced_and_Spatially_CVPR_2026_paper.html), agent-read). Action-centric physical commonsense is benchmarked as weak ([VideoPhy-2](https://arxiv.org/pdf/2503.06800), agent-read). Our decisive cues are fingers and paper-sized objects at a low pixel count.
- **Label control.** A prompt can't guarantee "counted, then handed over" or "handed over without counting". Every clip would need human verification, and anything the generator gets subtly wrong becomes a wrong label.
- **Risk.** A model can learn generator artefacts as the "violation" signal.
- **Cost.** 16 clips at ~9+ min each ≈ 2.5+ GPU-hours on a 24 GB card, competing with X2/X3 for the only GPU.
- **Verdict: avoid.** Re-staging gives real hands in the same 2 hours.

### D.E Counterfactual and hard-negative generation

- **Primary method:** the matched pairs in D.B. Keep scene, actors, length and start identical; change only the decisive act or its order. This is what prevents shortcuts like actor = label, duration = label, position = label.
- **Duration-matched clean sub-clips** (D.A, last row): label-safe and cheap; they break the duration shortcut for any learned component.
- **Splicing organizer clips** (e.g. cutting the counting step out to fake an omission): **don't.**
  - It creates jump-cut artefacts that are easier to detect than the omission.
  - The result is our label, not the organizers'.
  - It would never be ground truth.
- **Normative guard:** a counterfactual is labelled "violation" only when the mechanism has a clause or an organizer analogue (§D.B).

---

## E. Evaluation and leakage prevention

### E.1 Units and grouping (non-negotiable)

- **Unit = unique video (40), not file (42).** Merge Х-4/Х-47 and Х-5/Х-48 before any split or count.
- **Group key = scenario.** If X1 marks two clips as the same staged script (same actors and action, re-shot), they go into the same fold. Until X1 reports, assume no grouping beyond the duplicates, and say so.
- **Never let a label time choose a model's input** in a discovery experiment (landscape §E). Label-centred windows are allowed only in probes that are explicitly *verification* probes (X2), and those must include duration-matched clean windows at random times.
- **Normalise the container** (same re-encode for every clip) before any learned component sees pixels; that kills the bitrate cue.

### E.2 Protocol comparison

| Protocol | Meaningful here? | Why |
|---|---|---|
| A. Random video split | **No** | With duplicates and possible same-scenario re-shoots, it leaks. With n = 40, one 30/10 split puts 5 violation videos in test, so recall moves in 20-point steps. It produces confident-looking noise |
| B. Grouped split by scenario | Yes, **if** something is fitted | Needed for thresholds, prototypes, probes. Single splits are still noisy; prefer C |
| C. Leave-one-(group)-out | **Yes: the default for anything fitted** (thresholds, prototypes, linear probes, rule constants) | Uses all data; the per-video error list *is* the report. Reference floors: duration 25/40, timecode blind baseline (§A.2) |
| D. Leave-one-mechanism-out | Only if X1 finds **≥3 mechanisms with ≥2 unique videos each** | Tests the "unseen type" story for *learned* components. For a rule or checklist approach, an uncatalogued mechanism is missed by construction. LOMO then measures only the open "other" field, which is still worth knowing |
| E. Cross-camera on own staged footage | **Yes: the only robustness evidence** | Must never be used for tuning. Labels come from the shot script, **and** a second person confirms the act happened as scripted before scoring. Report it separately and call it indicative: it's a different room, desk, actors and props |

### E.3 Prompt and threshold overfitting (the realistic leakage for zero-shot work)

Iterating prompts on all 40 videos is tuning on all 40. Recommendation:
- **Dev set ≈ 2/3** (~14 violation + ~13 clean unique videos, stratified by duration) for prompt and threshold iteration.
- **Lockbox ≈ 1/3** (~7 + ~6), scored **at most twice** (mid-hackathon and at the freeze), always with the full config logged.
- Own other-angle footage is a second lockbox.
- Cost: the lockbox gives wide intervals (§E.5). It stops us from fooling ourselves about prompt gains; it can't rank close variants.

### E.4 Metrics

| Level | Metric | Notes |
|---|---|---|
| Video | TP / FN / FP / TN **counts**, recall on violation videos, **FP count on clean videos** | FAQ 16 reading: zero FN first, then minimise FP. Always list the failing video IDs |
| Event | Hit if a predicted `timecode_sec` falls within τ of a label; **report τ ∈ {1, 2, 3, 5} s as a curve**, under both the N.0 and N+0.5 conventions | Tolerance is undisclosed (FAQ 17). Compare against the blind baseline at every τ |
| Event | Extra events per violation video; false events per clean video | Extra events may or may not be penalised (unknown, E1) |
| Proposer | Label second covered by ≤K candidate windows (HX7) | Compare with the trivial proposer "windows centred on the relative-position prior" |
| Type | Human judgement: does the type match the X1 mechanism? | Not automatic; be honest that it's subjective |
| Evidence frame | Human judgement: does the frame show the act? | Same |
| Cost | Wall-clock per video, worst case | Hard limit 5 min |

### E.5 Small-sample uncertainty (Wilson 95 % intervals) [D]

| Observed | Interval | Reading |
|---|---|---|
| 7/10 | 0.40–0.89 | Can't separate from 50 % or from 85 % |
| 1/10 false yes | 0.02–0.40 | Could be a 40 % false-yes model |
| 0/19 FP on clean videos | 0.00–0.17 | Best possible evidence from our clean set |
| 20/22 events | 0.72–0.97 | |
| 9/22 (blind ±2 s) | 0.23–0.61 | |

Consequences: decide on **large** differences (roughly ≥3–4 videos out of 20) and on **qualitative failure analysis**; never on a one-video swing. With 21 violation videos, one miss is −4.8 points of recall.

### E.6 Do not

- Treat labels we create (X1 mechanisms, own-footage scripts) as independently verified ground truth. They're our hypotheses about the organizers' intent. Organizer labels are the only ground truth for the verdict and time, and only on organizer footage.
- Score own-footage results together with organizer results.
- Report a single accuracy number without the counts and IDs behind it.

---

## 8. Strategy comparison: no training vs. evaluation data vs. targeted adaptation

| | A. No additional training | B. Additional evaluation data | C. Targeted adaptation |
|---|---|---|---|
| What | Pretrained VLM/detector + prompts, sampling, crops, rules | Re-staged other-angle + hard-negative clips, used to **test** only | Prototypes / linear probe on frozen embeddings, or detector fine-tune on domain boxes |
| Expected benefit | Open vocabulary; no shortcut learning from labels; type and description come built in | Measures FP risk and viewpoint fragility; finds failure modes early | Can fix a specific perception gap (e.g. cash detection) where zero-shot fails |
| Data requirement | Dev/lockbox split of the 40 | 8–12 matched pairs × 2 views (§D.B) | ≥ a few hundred boxed frames (detector) or ≥5 unique videos per mechanism (prototype) [H] |
| Overfitting risk | Prompt overfitting (§E.3) | Low (not used to fit) | **High**: ~22 events, duration shortcut, one view |
| Domain shift | Unknown; overhead views likely rare in VLM training data [H] | It's how we measure it | Learns *this* camera; may hurt the new angle |
| Engineering effort | Already planned (X2/X3) | ~2 person-hours to record and label (§D.B) | 3–6 h including annotation [H] |
| Compute | Inference only | None extra | Training on a ~12 GB GPU: feasible for probes, tight for detectors [H] |
| Licensing | Model licences (exploration §2.1) | Own footage: clean | Public data with NC terms would taint shipped weights |
| Helps unseen types? | Some, via open vocabulary + catalog | Indirectly (staged B \ C′ rules test it) | **No**, by construction, for classifiers/prototypes; a better detector helps every rule that uses that object |

**Recommendation:** A as the main path, **B immediately in parallel**, and C only behind a gate.

**Evidence that would justify C (all four required):**
1. X1: humans can judge the mechanism at native resolution;
2. X2/X3: zero-shot fails on it consistently (e.g. ≤3/10 windows), and the failure is perceptual (object not found), not reasoning;
3. the mechanism recurs in ≥5 unique videos, or the fix is a reusable primitive (e.g. "cash in hand");
4. the adapted component beats both zero-shot **and** the blind baselines under leave-one-video-out, and doesn't get worse on own other-angle clips.

---

## F. Data investment ranking

Ranked by expected information gain per hour. H/M/L are judgements [H], not measurements.

| Rank | Action | Detection | FP | Localization | Robustness | Dev time | Compute | Annotation | Legal risk | Model-dependent? | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Extend X1 schema** (onset/peak/offset, mechanism, scenario ID, hard-negative moments, staging attributes, object px) | M | M | **H** | L | +15 min on X1 | none | +20–30 % X1 time | none | No | H |
| 2 | **Blind baselines + grouped scoring sheet** (duration 25/40; timecode prior; Wilson intervals) | M (prevents false wins) | M | **H** | L | 30–45 min | none | none | none | No | H |
| 3 | **Other-angle re-staging, small** (§D.B) | M | M | L | **H (only evidence)** | 1.5–2 h for 2 people | none | ~30 min | low (own footage, consent) | No | M |
| 4 | **Matched hard-negative pairs** (same session as 3) | L | **H** | L | M | +30 min on 3 | none | in 3 | low | No | M |
| 5 | **Degradation + sampling arms on X2/X3** (DX3, DX4) | M | L | M | M | 30–45 min of runtime | GPU minutes | none | none | Partly | M |
| 6 | Conventional augmentation (training) | L | L | L | L | 1 h | some | none | none | Only for C | M |
| 7 | Public banknote/HOI images for detector fine-tuning | L–M | M | L | L | 2–4 h | GPU hours | box checking | **check per dataset** | Only for C | L |
| 8 | Public surveillance/anomaly/procedural datasets | L | L | L | L | 2+ h download | disk | none | often NC | — | L |
| 9 | Generative video / simulation | L | L (risk of artefacts) | L | L | 4+ h | high | high | model licences | — | L |

**30 minutes of hard negatives vs. 2 hours of a generic surveillance dataset:** the hard negatives win on every column except "dataset size". They target the one failure that flips a clean verdict (a confident false event), they're licence-clean, and they're matched to our mechanisms. A generic surveillance dataset contains none of our mechanisms (§C).

**Parallel with model work:** ranks 1–2 run during X1 (no GPU). Rank 3–4 needs two people for ~2 h and can run while X2/X3 download weights. Rank 5 is an extra arm on probes that run anyway.

---

## G. Minimal experiment backlog

These extend X2/X3 instead of building a separate evaluation system. Scoring stays local; only counts leave the machine (exploration R10).

### DX1. Hard negatives vs. ordinary negatives

- **Question:** does the verifier's false-yes rate depend on look-alike actions rather than on clean footage in general?
- **Hypothesis:** false yes on matched hard negatives > on random clean windows by ≥3/10.
- **Data:** 10 random clean windows (X2 already has them) + 8–10 hard-negative windows: own matched pairs (§D.B), plus any look-alike moments X1 finds in clean organizer clips.
- **Procedure:** X2 arm B (checklist + negative control), same prompt and sampling, blind order.
- **Baseline:** X2's ordinary clean windows.
- **Metrics:** false yes per set; which checklist item fired.
- **Success:** hard-negative false yes ≤2/10 → FP control is adequate.
- **Failure:** ≥4/10 → FP is driven by look-alikes. Add per-rule evidence requirements, negative-control prompts, or a second independent cue before claiming.
- **Cost:** ~20 min of runtime after the recording session.
- **Decision changed:** how much FP machinery the pipeline needs. It also tells us whether training-set FP rates mean anything.

### DX2. Overhead vs. other angle (= E7b, quantified)

- **Question:** do the cues survive a viewpoint change, for humans and for the model?
- **Hypothesis:** for relational mechanisms (M1/M2/M6-type), human judgeability and model detection hold. For small-object mechanisms (M3/M4/M7-type), both drop.
- **Data:** own clips, each act recorded **simultaneously** from an overhead-ish phone and a second phone at another angle (§D.B), so the only difference is the viewpoint.
- **Procedure:** (1) a person who didn't act judges each clip from the new view alone; (2) the same X2/X3 probe runs on both views.
- **Baseline:** the same act from the overhead phone.
- **Metrics:** per mechanism, judgeable yes/no (human); hit/miss and false yes (model); cues named.
- **Success:** model hits on the new view ≥ (overhead hits − 1) for a mechanism.
- **Failure:** human or model loses the mechanism on the new view → declare it viewpoint-fragile. Use different cues or report the limitation.
- **Cost:** recording in DX1's session; ~30 min of scoring.
- **Decision changed:** which rules we claim are robust; whether the pipeline needs viewpoint-independent primitives (relational predicates, VLM scene questions) instead of zones.

### DX3. Resolution and compression sensitivity

- **Question:** does the probe's success depend on pixel detail, which would make crops worth building? Or is it insensitive, meaning the evidence is coarse?
- **Hypothesis:** for cash-related events, X3 cash detection and X2 mechanism correctness fall when the frame is downscaled 0.5× + re-encoded at a low bitrate, and rise with 2× crops around the hands.
- **Data:** X2/X3's labelled windows in three variants: native, degraded, crop-upscaled. Generated locally with ffmpeg.
- **Procedure:** rerun X2 arm A/B and X3 OWLv2 on all three.
- **Baseline:** native.
- **Metrics:** mechanism correct /10; cash recall; false detections.
- **Success (crops matter):** crop > native by ≥3/10 → invest in a crop stage.
- **Failure (no sensitivity):** all within ±1 → cash identity isn't what the model relies on. Check that it isn't relying on shortcuts (DX1/X1).
- **Cost:** ~30 min of runtime.
- **Decision changed:** whether a crop/zoom stage is worth it; which augmentations are label-preserving (if 0.5× kills the evidence, 0.5× is not a safe augmentation).

### DX4. Temporal sampling density

- **Question:** at what frame rate are the decisive hand actions captured?
- **Hypothesis:** 1 fps misses ≥3/10 short transfer events that 4 fps catches.
- **Data:** X2 labelled windows.
- **Procedure:** the same X2 prompt at 1, 2 and 4 fps within the window, and the whole-clip run at 1 vs 2 fps.
- **Baseline:** 1 fps.
- **Metrics:** mechanism correct; timestamp error vs. the blind baseline; latency; VRAM.
- **Success:** a rate that keeps a 145 s clip inside the budget with no recall loss → fixes the sampling policy.
- **Failure:** short events need a rate the budget can't afford for whole videos → evidence for a proposer + dense-window cascade (F4).
- **Cost:** ~30 min of runtime.
- **Decision changed:** F3 vs F4; the frame budget.

### DX5 (conditional). Zero-shot vs. few-shot adaptation

- **Run only if** the §8 gate conditions 1–3 hold for some mechanism.
- **Question:** does a prototype or linear probe on frozen embeddings beat zero-shot on that mechanism without learning the shortcut?
- **Data:** windows from the mechanism's videos vs. duration-matched clean windows; leave-one-video-out.
- **Baselines:** zero-shot (X2), duration-only (62.5 %), relative-position prior.
- **Success:** beats all three by ≥3 videos and holds on own other-angle clips.
- **Failure:** ties a baseline → don't adapt.
- **Cost:** 1.5–2 h.

---

## H. Final recommendations

**Do immediately (no dependence on model choice):**
1. Add the §I columns to X1 before the footage pass starts.
2. Merge duplicates, fix the dev/lockbox split, and adopt the blind baselines (§A.2) as the floor in every scoring sheet.
3. Schedule one 2-hour recording session (2 people) for other-angle + matched hard-negative clips (§D.B), right after X1 names the mechanisms. If X1 runs late, record the provisional M1/M2/M3 pairs anyway: they're cheap and generic.
4. Send E1 to the organizers with one added question: *does the new-angle test video come from the same room and desk?*

**Only if a model experiment fails:**
- X3 can't find cash but humans can (X1) → consider DX5 / detector fine-tuning on **locally boxed organizer frames** (licence-clean, domain-matched) before any public banknote dataset. Then check that dataset's licence word for word.
- DX4 shows short events need dense frames → spend data effort on a proposer-recall test set (onset/offset annotations), not on more clips.
- DX1 shows a look-alike FP problem → record more hard negatives for the offending mechanism (30 min each).

**Defer:**
- Any public dataset download (§C) until a specific failure points to it.
- Conventional augmentation, unless strategy C is triggered.
- Leave-one-mechanism-out, until X1 shows enough mechanisms.

**Avoid entirely:**
- Generic anomaly datasets as a source of "violations".
- Generative video and 3D simulation for training (§D).
- Training shipped weights on data with non-commercial or unclear terms.
- Uploading organizer clips, frames, or per-clip descriptions to any cloud tool. That includes cloud labelling tools and asking a cloud assistant to write the re-staging script from the X1 sheet: **X1's per-clip notes are frame descriptions** (brief §7). Write re-staging scripts from the generic mechanism rows (§B), which come from the brief and public rules.

---

## I. Handoff to problem validation (X1, X2, X3)

| Experiment | What this report adds | Why |
|---|---|---|
| **X1** (human footage pass) | Extra columns per event: **onset / peak / offset** (to 0.5 s); **mechanism ID** (from §B, or new); **scenario ID** (same staged script = same ID); actor/costume set (descriptive only, no identification); **people count**; **hard-negative moments** in clean clips (time + what it resembles); "anything suspicious" in clean clips; **object px size** at the decisive moment; label offset relative to the act; occlusion yes/no; whether the event could be judged from a single frame. For Х-4: both times | Unlocks localization scoring (§E.4), grouping (§E.1), the confound check (§A.2), hard-negative inventory (DX1), and the data gap matrix (§B.2) |
| **X2** (local VLM probe) | Add DX1's hard-negative windows; DX3's degraded/crop variants; DX4's 1/2/4 fps arms. Score timestamps **against the blind baseline**, not only against ±2 s. Respect the dev/lockbox split | Turns X2 from "does it work" into "what does it depend on" |
| **X3** (perception + proposer) | Compare proposer recall with the trivial relative-position proposer. Cash recall at native vs. crop (DX3). Run on own other-angle clips (DX2) | The proposer must beat a pixel-free prior to earn its place |
| HX5 | Re-state the bar: "within ±2 s in ≥7/10 **and** above the blind baseline (9/22 ≈ 41 % at ±2 s)" | 7/10 has a Wilson interval of 0.40–0.89 and overlaps the blind rate |
| HX9 | Now testable via DX2, at the level "indicative on own footage" | |

---

## 11. Critical review of assumptions

| # | Assumption | Verdict |
|---|---|---|
| 1 | More training data will solve the problem | **False here.** Binding problems are annotation, viewpoint, FP look-alikes, pixel scale and norms (§0). More of the same view adds little |
| 2 | Public surveillance datasets transfer to banking | **Unsupported.** No public dataset contains bank cashier procedures (§C). Generic actions (walk, carry, hand over) transfer at best as primitives |
| 3 | Synthetic video increases generalisation | **Unsupported for our case** (§D): hand and small-object artefacts, no label control |
| 4 | Image augmentations simulate camera-angle changes | **False.** A 2D warp of an overhead image can't reveal what an oblique camera sees (occlusion order, the side of the counter, faces of objects) |
| 5 | A balanced training set implies balanced test performance | **False.** The test has 5+ videos of unknown balance; clean and violation videos fail in different ways (reframing §4.1) |
| 6 | Higher resolution guarantees better action recognition | **Unproven.** Test footage is 464×848 anyway; DX3 measures whether detail matters |
| 7 | More detailed annotations are always worth their cost | **No.** Onset/offset, mechanism and scenario ID are cheap and decisive. Per-frame boxes and masks are expensive and only pay off under strategy C |
| 8 | A specialised trained model is necessary | **Unproven**; §8 gives the evidence that would justify one |
| 9 | Generic abnormal events = compliance violations | **False.** Anomaly datasets label crimes and accidents. A procedural violation can look perfectly normal, and an unusual action can be legitimate (reframing §4.3) |
| 10 | Better detection of hands or money improves violation classification | **Only if the mechanism hinges on that object.** M1/M2/M6-type rules depend on presence and dwell, not on cash identity. Better detection also raises the false-positive rate on legitimate cash handling unless the temporal rule is right |
| + | The organizers' labels mark the act's onset | Unknown; might be peak or completion (§A.3) |
| + | Clean clips are free of any violation | Unverified [P] |
| + | Own staged footage resembles the test's new angle | Unknown. It's a different room, desk and actors, so it's indicative only |
| + | Script labels for own footage are correct | Actors deviate. A second person must confirm each clip |
| + | Prompt iteration on all 40 videos is "zero-shot" | It's tuning (§E.3) |
| + | A dataset is usable because it's downloadable | Licences vary, and many are NC or require an agreement (§C) |

---

## 12. Remaining unknowns

- Mechanisms and their recurrence (X1).
- Whether clean clips contain hard negatives (X1).
- Label convention and the Х-4 double label (X1).
- Whether the test's new angle is the same room (E1).
- Whether other-angle own footage predicts jury-video behaviour: it can't be validated before judging.
