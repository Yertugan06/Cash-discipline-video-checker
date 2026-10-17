# Attempts

One folder per approach we tried, with what it was, what it scored and where its logs are.
Add a row here and a folder (copy `_template/`) for every new attempt, including failed ones.

Logs go in each attempt's `logs/` folder, per-video detail included (this repo is a draft, see
`CONTEXT.md`). Anything too large stays on the VM, linked by path.

## Map

All runs are on the 40 unique open videos (21 with a violation, 19 clean), 2026-10-17.
"Correct" is the whole-video verdict. "Clean FP" is clean videos wrongly flagged.
"Timecode" is labelled events matched within the given window (22 events).
"R1 validation" = `reasearch1/validation-evidence/` (pre-registered harness and scorer, write-up in
`reasearch1/problem-validation.md`). It also re-scored A01 and A02 with its own scorer and got the
same numbers (`reasearch1/validation-evidence/logs/arch_rescore_teammates.txt`).

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
| [A13](A13-detection-spike/) | teammate (datathon) | Spike: can open-vocabulary detectors or a VLM see the objects on 20 hand-labelled frames | OWLv2, Grounding DINO, Qwen2.5-VL-7B | n/a | per-frame checks: OWLv2 17/33, GDINO 13/33, VLM 21/33 | - | - | 4.1 s per frame (VLM) | measured; cash seen 4/11 by all |

## Takeaways so far

- Nothing has clearly beaten "always violation" (21/40). Best is A04 F3-whole at 23/40,
  inside the ±2-video tie band from the pre-registration.
- Every approach that flags often (A01, A02, A06) has 68-100% clean false alarms. The brief
  puts false alarms right after misses.
- Zero-shot VLMs don't tell a real event from its clean twin (A08), at 4B or 8B.
- The missing piece is targeted perception of small objects (cash, keys, screen, door);
  see `reasearch1/problem-validation.md` §9.

## Next to run

- A12 on all 40 videos through the API (`eval/run_eval.py`); this is the number the
  detector decision needs.
