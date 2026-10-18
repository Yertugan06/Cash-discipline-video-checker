# Attempts

One folder per approach we tried, with what it was, what it scored and where its logs are.
Add a row here and a folder (copy `_template/`) for every new attempt, including failed ones.

Logs go in each attempt's `logs/` folder, per-video detail included (this repo is a draft, see
`CONTEXT.md`). Anything too large stays on the VM, linked by path.

## Map

The common dataset has 40 unique open videos (21 with a violation, 19 clean),
42 file aliases. Runs span 2026-10-17/18; individual rows distinguish file/unique counts.
"Correct" is the whole-video verdict. "Clean FP" is clean videos wrongly flagged.
"Timecode" is labelled events matched within the given window (22 events).
"R1 validation" = `validation/validation-evidence/` (pre-registered harness and scorer, write-up in
`archive/research1/problem-validation.md`). It also re-scored A01 and A02 with its own scorer and got the
same numbers (`validation/validation-evidence/logs/arch_rescore_teammates.txt`).

| ID | Source | Approach | Models | Correct /40 | Recall | Clean FP | Timecode | Worst runtime | Status |
|---|---|---|---|---|---|---|---|---|---|
| [A00](A00-baselines/) | R1 validation | Floors: always "violation", pixel-free priors | none | 21 | 21/21 | 19/19 | ±3 s 12/22 (position prior, shortcut) | - | reference |
| [A01](A01-f1-cv-checker-v1/) | teammate (datathon) | F1 CV checker v1: detectors + tracking + 21 temporal rules | RT-DETR, OWLv2, CLIP, RTMPose, ByteTrack | 20 | 14/21 | 13/19 | ±2 s 10/22, ±5 s 11/22 | 294.6 s | measured, superseded by A12 |
| [A02](A02-vlm-qwen35-9b-questionnaire/) | teammate (datathon) | VLM per-frame questionnaire (1 fps) + timeline rules | Qwen3.5-9B FP8 (vLLM) | 22 | 19/21 | 16/19 | ±1 s 8/22, ±3 s 13/22 | **344.2 s (over limit)** | measured |
| [A03](A03-vlm-qwen35-9b-prompts-v2/) | teammate (datathon) | A02 with prompts v2, 1024 px, zoom crops | Qwen3.5-9B FP8 (vLLM) | - | - | - | - | - | gold frames only; full run stopped at 5 videos |
| [A04](A04-f3-whole-video-vlm/) | R1 validation | F3: whole clip or 30 s chunks into a video VLM | Qwen3-VL-4B | 23 / 20 | 8/21, 9/21 | 4/19, 8/19 | top-1 ±3 s 0/22 | 149.5 s | measured, rejected |
| [A05](A05-f4-cascade/) | R1 validation | F4: motion or uniform proposer, then VLM verifier | Qwen3-VL-4B | 20 / 20 | 8/21, 10/21 | 7/19, 9/19 | top-1 ±3 s 1/22 | 44.1 s | measured, rejected |
| [A06](A06-f1-zone-free-coco/) | R1 validation | F1 probe: COCO detector + zone-free rules | RT-DETR v2 r18 | 21 | 21/21 | 19/19 | top-1 ±3 s 5/22 | 113 s (CPU) | measured, rejected |
| [A07](A07-f2-embedding-probe/) | R1 validation | F2: frozen image embeddings + linear probe | DINOv2-base, SigLIP2-base | 18-21 | 5-17/21 | 3-17/19 | ties the prior | - | measured, rejected |
| [A08](A08-vlm-window-verifier/) | R1 validation | "Is there a violation in this 8 s window?" vs clean twins | Qwen3-VL-4B, Qwen3-VL-8B | n/a | 8/22, 16/22 windows | 4/19, 15/19 twin windows | - | - | measured, no discrimination |
| [A09](A09-kit-rule-sweep/) | R1 validation | Re-tune A02's rules on dev, score lockbox once | (A02 states) | dev 16/24, lockbox 8/16 | lockbox 6/9 | lockbox 5/7 | lockbox ±3 s 3/10 | - | measured, no gain |
| [A10](A10-agentA-rulebook/) | agentA (datathon2) | Rulebook variant of the F1 checker | as A01 | - | - | - | - | - | ran on dev, **no score recorded** |
| [A11](A11-agentB-hybrid/) | agentB (datathon) | Hybrid: F1 detections + VLM probes at anchors | F1 stack + Qwen VLM | - | - | - | - | - | ran on dev, **no score recorded** |
| [A12](A12-adr002-service-f1/) | ADR-002 service | ADR-002 service, `DETECTOR=f1`, evidence boxes (live on `datathon`) | as A01 | - | - | - | - | - | **not evaluated on 40 yet**; 1-video smoke test |
| [A13](A13-detection-spike/) | teammate (datathon) | Spike: can open-vocabulary detectors or a VLM see the objects on 20 hand-labelled frames | OWLv2, Grounding DINO, Qwen2.5-VL-7B | n/a | per-frame checks: OWLv2 17/33, GDINO 13/33, VLM 21/33 | - | - | 4.1 s per frame (VLM) | legacy 4/11 cash accuracy is not recall; re-score: OWLv2/VLM 0/7 cash TP |
| [A14](A14-glass-reflection-fix/) | agent (datathon) | A12 + glass-reflection filter, laptop-desk calibration, near/far cashier split; per-job traces, replay, /compare | as A01 | 23/42 (files) | 9/22 | 6/20 | - | 146.6 s | live; outsider on clean 10 -> 0, misses up |
| [A15](A15-vlm-roles-spike/) | agent (datathon) | Spike: per-person role + situation from one frame with numbered boxes | Qwen2.5-VL-7B (bf16) | n/a | cashier right in 5/21 two-person frames | - | - | 6.4 s per frame (median) | measured; rejected (swaps cashier and client) |
| [A16](A16-cashier-side-from-lone-person/) | agent (offline replay) | Cashier side = where a lone person works at the laptop (any camera angle) | as A14 | 21/42 (files) | 15/22 | 14/20 | - | - | measured offline, not deployed; roles right on front-facing cameras, exposes leave-rule FPs |
| [A17](A17-leave-rule-fixes/) | agent (datathon) | A16 + leave rules: laptop not a tablet, away = out of laptop reach, item still on desk 2 s later | as A14 | 26/42 (files) | 12/22 | 6/20 | - | 144.4 s | live; replay = live on all 42 files |
| [A18](A18-desk-object-history/) | agent (offline replay) | Desk objects by history: items found by desk change (emptiest moment of the clip as background), named only when 2 clues agree (origin zone, counter ran, detector label) | as A14 + OpenCV | 22/40 (replay; A17 25) | - | 6/19 (A17 5) | - | 74 s for 40 clips (CPU) | rejected: failed the agreed bar; "any item left" cuts misses 10 -> 7 but clean FP 5 -> 9 |
| [A19](A19-desk-objects-strict-origin/) | agent (offline replay) | A18 + strict origin (hand inside the open safe / on the counter) + blob shape filter; pre-registered, one run | as A18 | 22/40 (replay) | - | 5/19 | - | ~75 s for 40 clips (CPU) | rejected: 13 missed; naming items from history doesn't beat the detector without new labels |
| [A20](A20-night-orchestration/) | orchestrator + Codex agents (offline replay, API check on datathon) | Verified rule fixes on F1 (door entry, personal-item gaps and equipment, client sessions, leave evidence, desk-relative scale, collector visit, timecode ranking) + robustness probes; merged with fix-dataset | as A14 | **32/40** (replay) | 13/21 | **0/19** | ±1/3/5 s: 7/11/13 of 13 caught | - | merged to main; zoom/mirror/drop stable |
| [A21](A21-deadline/) | orchestrator + four remote workers | Evidence guards, observed doorway-hand exit correction, independent explanation audit; local state verifier enabled at user request after measurement | existing local F1 stack; Qwen3-VL-4B diagnostic | **30/40** (real API) | 11/21 | **0/19** | compatible human timing mostly unannotated | median 2.0675 s mostly cached; X20 cold 50.669 s | one-VM VLM-enabled release; 9 compatible / 0 contradicted / 3 unknown findings; [results](A21-deadline/RESULTS.md) |
| [A22](A22-left-during-service-replay/) | agent (offline replay on datathon) | New rule L-LEFT-DURING-SERVICE (231 п. 22) from the legal review, baseline vs + rule on the same code; re-run after merging A21 | (cached F1 perception) | 32 / 32 before A21, 30 / 30 after | 13/21, then 11/21, unchanged by the rule | 0/19 | unchanged | 3.3 s replay | measured, 0 findings (no cashier exit during a client session in the open clips); rule stays disabled |
| [A27](A27-zero-shot-cash-detectors/) | agent (datathon) + user box review | Zero-shot cash detectors with commercial licenses on the 12 A24 presence frames, one prompt per pass, full frame + tiles; user marked each top box | OWLv2-base, OWLv2-large, MM-Grounding-DINO-large (SAM 3 gated, not run) | n/a | top box on cash: OWLv2-base 7/7, OWLv2-large 7/7, MM-GDINO 0/7 | wrong box above thr: 1 / 0 / 12 of 12 | - | 2.7 / 12.6 / 22 s per frame (15 passes) | measured; A13's 0/7 was label competition ("id card" wins); runtime labels cash `id_card` in 4/7 |

## Current conclusions

- A21 is the active one-VM review release: 30/40 unique verdict agreement, 0/19 clean
  false alarms, 10/21 misses. A20's historical 32/40 included two contradicted explanations.
  Supported findings remain 9; improved auditing has not improved detection accuracy.
- Local Qwen3-VL-4B safe checks are enabled at the user's request. The measured comparison
  added no correct detections. Door checks failed a clean control and remain diagnostic.
- A13's historical 4/11 cash accuracy came mainly from negatives. The re-score records
  OWLv2/Qwen2.5-VL-7B cash TP 0, FN 7, TN 4; Grounding DINO TP 1, FN 6, TN 3, FP 1.
- A27 qualifies that: asked about banknotes alone, OWLv2-base puts its top box on cash in 7/7
  (user-checked). Running all prompts in one pass lets "id card" win on the cash box; the
  runtime's `objects()` labels the cash `id_card` in 4/7 frames. Fix label competition first.
- A21's native-tile object probe adds no cash detections beyond the existing full+desk
  inputs. The 4B temporal probe leaves most cash cases unknown and adds one false ID.
- A08 already tested 4B/8B generic violation-window prompts without useful clean-twin
  discrimination. A larger model is not a demonstrated fix; test a specific observation
  capability before adding it to runtime.
- Desk-change/history naming failed in A18/A19 and stays disabled. Missing detections,
  brief occlusion and recording cutoff do not justify inferred failures.
- All public clips influenced development. Cached geometry probes do not establish
  unseen-camera or unseen-scenario accuracy.

## Next priorities

1. Recover supported observations for cash at a client change and safe attendance/open
   state, with unchanged rules across all clips and clean controls. No filename/time or
   annotation lookup exceptions.
2. Compare any model/input change on a fixed prompt/manifest and record unknowns,
   false positives, latency and same-VM memory; promote only measured useful changes.
3. Complete human norm/source verification before jury scope is enabled. X1/X2's causes
   and the blanket ID-first policy remain unresolved.
