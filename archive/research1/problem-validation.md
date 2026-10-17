# Problem Validation — Datathon 26 (ForteBank)

Status: **complete for this round, 2026-10-17 ~19:30.** 9 detector configurations across F1, F2, F3 and F4 (plus 2 F0 floors) were measured on all 40 unique videos, plus 5 window-level verification probes. **None separates violation videos from clean videos, and none localizes better than a pixel-free prior.** The F3 vs. F4 vs. F1 comparison is therefore a tie at chance. The decision and switching conditions are in `solution-decision.md`.

Inputs: `task.md`, `problem-reframing.md` (rev 5), `problem-exploration.md`, `data-exploration.md`, `technology-research-landscape.md`, `senior-ideas.md`, `archive/skills/problem-validate/SKILL.md`, `data/Таблица_нарушений.xlsx`, `data/Cash_Discipline_Cases_Rules.xlsx`.

**Evidence labels:** **[M]** measured here (script + log under `validation/validation-evidence/`) · **[R]** reproduced independently · **[Rep]** reported by others, not reproduced · **[H]** hypothesis.

**Privacy:** inference ran only on team-controlled machines: the laptop RTX 4080 12 GB, and the Brev L4 `datathon2`, a team VM the user directed the work to. No frame, video, model description or per-clip annotation was sent to a cloud AI; scripts print aggregates only. Per-clip ground truth, predictions and raw model text are in `validation/validation-private/`.
**⚠ That folder and both annotation workbooks were pushed to the public GitHub repo in commit `8155025`** (§13).

## 1. Environment, data and protocol

| Item | Value |
|---|---|
| Laptop | RTX 4080 Laptop 12 GB; WSL 9.7 GB RAM; torch 2.14.1+cu126, transformers 5.20.1 (`validation/validation-evidence/harness/requirements-lock.txt`) [M] |
| `datathon2` | NVIDIA L4 23 GB (dedicated), 15 GB RAM, 4 vCPU; torch 2.11.0+cu128, transformers 5.20.1 (`validation/validation-evidence/logs/datathon2/requirements-lock-datathon2.txt`) [M] |
| Models (all Apache-2.0, pinned, SHA-256 verified) | Qwen3-VL-4B-Instruct `ebb281ec`; Qwen3-VL-8B-Instruct `0c351dd0`; RT-DETR v2 r18 `56509617`; DINOv2-base `f9e44c81`; SigLIP2-base-patch16-384 `f775b65a` |
| Workbook | `data/Таблица_нарушений.xlsx` (sheets Нарушения / Без нарушений / Нормы). **No `Таблица_нарушений(1).xlsx` exists in the project**; the file present matches the latest download. It was edited at 15:43 (2 norm codes, confidence and must-check flags). All scores below are recomputed on the edited version; every number came out identical to the pre-edit scoring (`validation/validation-evidence/logs/score_all_gtv2.txt`, `validation/validation-evidence/logs/datathon2/*gtv2.txt`) |
| Ground truth | Verdict and time: organizer labels only. Mechanism: human norm code on the **mechanism-reliable subset (17/21 violation videos)**. It excludes X-1, X-11, X-13 and X-44, and rows flagged ОБЯЗАТЕЛЬНО unless re-reviewed (X-24 and X-32 count as reviewed). Human times equal the organizer seconds within 1 s for 22/22 events [M], so the workbook adds mechanism, not timing |
| Units, groups, split | 40 unique videos (21 V / 19 C), 22 events. **22 groups** = byte duplicates (X-4≡X-47, X-5≡X-48) + violation/clean twins from the workbook. Dev 24 (12/12) / lockbox 16 (9/7), grouped and layout-stratified, seed 26 [M, R] |
| Camera layouts | 3 layouts in `Cash_Discipline_Cases_Rules.xlsx`. Every score is reported per layout. This is **cross-layout within one camera style; no other-angle footage exists**, so no cross-view robustness claim is made |
| Shortcut controls | No system receives duration, relative position, clip identity or label times. The duration-only verdict (LOO 25/40; video AUC 0.68) and the relative-position timecode prior are **references only** |
| Pre-registration | `validation/validation-evidence/PREREGISTRATION.md`: claims C1–C6 before any output; Addendum A (A1, A2) before those runs; Addendum B (B1) before the probes |
| Verification | An independent agent reproduced GT counts, duplicates, split integrity and the scorer on synthetic predictions (`validation/validation-evidence/verify/`) [R]. The pixel-free baselines were reproduced from the original audit script [R]. Qwen3-VL-4B verification reproduced **identically** on the L4 (8/22, 4/19, 2/11, 5/19; greedy decoding) [R] |

## 2. Floors every candidate must beat

| Floor | Verdict (40) | Top-1 timecode ±1/2/3/5 s (22) |
|---|---|---|
| Always "violation" (F0 compliant floor) + top motion peak | 21/40 (recall 21/21, clean false alarms 19/19) | 4/6/7/9 |
| Duration threshold, LOO (**shortcut**, reference) | 25/40 | — |
| Relative-position prior (**shortcut**, reference) | — | 3/9/12/17 (group-LOO); 4/9/12/18 (video-LOO) |
| Motion-threshold verdict, group-LOO | 14/40 | — (below chance: motion carries no verdict signal) |

## 3. Candidates screened

| Family | Status |
|---|---|
| **F3** whole-video local VLM | Finalist: 2 configs × 4B |
| **F4/D** coverage-first cascade | Finalist: 2 proposers × 4B verifier; verifier also tested at 8B |
| **F1** structured CV + temporal rules | Zone-free COCO probe measured. The teammate's full F1 app (`forte-cash-checker`: OWLv2 + CLIP crop states + RTMPose + tracking, 16 rules) is the real contender: **[Rep]**, not reproduced |
| **F2** frozen embeddings + linear probe | Excluded at exploration; **re-admitted by the data-exploration §8 gate** after zero-shot failed (Addendum B). 2 encoders × centred/raw |
| F0 | Floor |
| Novelty detection, end-to-end supervised classifier, generative or synthetic data | Excluded (exploration §5; data-exploration §D) |

## 4. Results: video level (all 40; dev / lockbox)

| Approach | TP / FN / FP / TN | Correct | Dev · Lockbox | Top-1 ±2 s / ±3 s | Mechanism (17) | Worst runtime |
|---|---|---|---|---|---|---|
| F3 whole clip 1 fps 288 px, 4B | 8 / 13 / 4 / 15 | 23 | 15/24 · 8/16 | 0 / 0 | 6 anywhere, 1 at ±3 s | 149.5 s |
| F3 30 s chunks 2 fps, 4B | 9 / 12 / 8 / 11 | 20 | 12/24 · 8/16 | 0 / 0 | 5, 0 | 30.4 s |
| F4 motion top-5 → 4B verifier | 8 / 13 / 7 / 12 | 20 | 12/24 · 8/16 | 0 / 1 | 3, 2 | 44.1 s |
| F4 uniform top-5 → 4B verifier | 10 / 11 / 9 / 10 | 20 | 11/24 · 9/16 | 1 / 1 | 4, 2 | 41.4 s |
| F1 zone-free COCO rules | 21 / 0 / 19 / 0 | 21 | 12/24 · 9/16 | 4 / 5 | 2, 0 | 113 s (CPU) |
| F2 DINOv2, centred | 17 / 4 / 15 / 4 | 21 | 14/24 · 7/16 | 7 / 8 | — | (features 2 fps) |
| F2 DINOv2, raw | 16 / 5 / 17 / 2 | 18 | 12/24 · 6/16 | 6 / 7 | — | |
| F2 SigLIP2, centred | 12 / 9 / 10 / 9 | 21 | 13/24 · 8/16 | 3 / 6 | — | |
| F2 SigLIP2, raw | 5 / 16 / 3 / 16 | 21 | 14/24 · 7/16 | 2 / 3 | — | |

**Per-layout rows** (`logs/score_*.txt`, `logs/datathon2/score_F2_*.txt`) show no layout where any candidate works. C6 can't be tested while nothing works on any layout.

**Threshold-free F2 view** (`logs/datathon2/F2_*.txt`): video AUC of the max window score is **0.49–0.54** for all four variants. That is below the duration shortcut's 0.68. Window AUC for label vs. matched-twin windows: DINOv2 0.62 / 0.67 (raw); SigLIP2 0.49 / 0.64 (raw); n = 22 vs. 19. The best argmax localization is DINOv2 centred, at ±2 s 10/22 and ±3 s 11/22, **a tie with the blind prior** (9/22, 12/22). Pre-registered bar (twin and video AUC ≥ 0.70, beat the prior): **not met.**

## 5. Results: verification on labelled windows

8 s windows (label ±4 s), 4 fps, 448 px. Matched twin = same time in the clean clip of the same staged group.

| Model / prompt | Labelled | Matched twin | Random clean | Off-event | Names the human mechanism: labelled vs. twin |
|---|---|---|---|---|---|
| 4B, checklist (laptop) | 8/22 | 4/19 | 5/19 | 2/11 | 3/19 vs. 1/15 |
| 4B, checklist (L4; reproduction) | 8/22 | 4/19 | 5/19 | 2/11 | 3/19 vs. 1/15 |
| **8B bf16, checklist (A1)** | **16/22** | **15/19** | **14/19** | **8/11** | 7/19 vs. 3/15 |
| 4B, per-item yes/no, dev (A2) | 4/12 | 2/10 | 2/12 | 3/6 | 1/11 vs. 0/8 |
| 8B, per-item yes/no, dev (A2) | 2/12 | 3/10 | 3/12 | 2/6 | 1/11 vs. 1/8 |

- 4B time error on its yes answers: median 4.0 s (0/8 within ±2 s). 8B: median 2.0 s, which is what random placement inside an 8 s window gives.
- Peak VRAM: 4B 10.0 GB, 8B 18.4 GB. Per window: 6–9 s, or 15–21 s with the per-item prompt.
- **Reading:** the 4B rarely says "violation"; the 8B says it about 75 % of the time on every set. Neither separates real events from their matched clean twins. The per-item prompt removes the 8B's yes-bias but not the lack of discrimination. The only residual signal is the 8B naming the right mechanism (7/19 vs. 3/15), and its Wilson intervals overlap. **A1 falsified: the failure is not a capacity artefact at 4B→8B.** A2: no gain on dev, so no lockbox run was spent.

## 6. Proposer recall [M]

| Proposer | K | ±W | Events covered | Mean coverage (violation clips) |
|---|---|---|---|---|
| Motion "short" | 3 / 5 / 8 | 2 s | 18 / 20 / 21 of 22 | 0.56 / 0.72 / 0.76 |
| Uniform | 3 / 5 / 8 | 2 s | 15 / 19 / 21 of 22 | 0.59 / 0.86 / 0.93 |

- Motion beats uniform placement at equal K. But clips are short (violation median 20 s), so 20/22 already needs about 70 % coverage.
- The F4 results are identical with motion or uniform windows.
- The proposer matters only on long clips. Its value there is unmeasured, because the dataset has none with events.
- Compute: 38 s CPU for 21.6 min of footage.

## 7. Feasibility (C1) [M]

Every configuration finishes within the 5-minute limit. The binding factor is output length, not video length.

| Measurement | Value |
|---|---|
| 4B load | 94–127 s cold (once per service start) |
| Whole 142 s clip, 4B | 11k tokens, 13 s prefill; 149.5 s worst end to end, because decode slows near the 12 GB ceiling |
| 30 s chunks, 4B | 30 s worst clip |
| 8B on the L4 | 18.4 GB peak per 8 s window; ~8.5 s median |

## 8. Claim register: outcome

| ID | Claim | Outcome |
|---|---|---|
| C1 | Local VLM processes the longest clip within budget | **Holds [M]** |
| C2 | F3 discovers events better than the floors | **Falsified [M]**: recall 8–9/21, top-1 ±3 s 0/22 vs. prior 12/22 |
| C3 | VLM verifier separates labelled windows from matched twins | **Falsified [M]** at 4B and 8B, under both prompts |
| C4 | Motion proposer beats uniform at equal coverage | **Holds weakly [M]**; no downstream value while the verifier is at chance |
| C5 | Zone-free COCO rules separate classes | **Falsified [M]**: every rule fires equally on clean clips |
| C6 | Results hold across layouts | **Untestable**: nothing works on any layout. No cross-view evidence exists |
| A1 | Larger VLM fixes recognition | **Falsified [M]**: the 8B gains yes-bias, not discrimination |
| A2 | Per-item prompt helps | **Falsified on dev [M]** |
| B1 | Generic frozen features + linear probe recover the signal (LOGO) | **Falsified [M]**: video AUC 0.49–0.54 < duration shortcut 0.68 |

## 9. Why everything fails: the mechanism (interpretation, labelled)

- **[M]** Matched twins share actors, staging, layout and timing. A detector only scores if it sees the **specific decisive state**: cash left on the workplace (norm 231-20-2, 8/22 events), door open (14-16-1, 3), keys or seals left out (231-80, 2), unlocked screen (48-71-9, 2), ID or count steps.
- **[M]** Generic perception gets nothing from that difference:
  - VLM answers barely depend on the window content.
  - COCO objects are background.
  - Global embeddings don't separate twins.
- **[H]** The decisive cues are small (cash/keys about 20–40 px, exploration N3) and local. A global image or video representation averages them away. Only perception targeted at a specific object state in a specific place (desk surface, door, screen, drawer) has a plausible path. That is what the teammate's F1 app attempts. **It is unverified here.**

## 10. ATAM-lite

| Scenario | F3 / F4 (VLM) | F1 generic | F1 mechanism-specific (teammate) [Rep] |
|---|---|---|---|
| Cash left on the desk, short clip → flag within ±3 s | Fails (§5) | Fails (§4) | Reported miss on X-26 (CPU, 0.5 fps); full run unverified |
| Matched clean twin → silent | 4B ok by rarely saying yes; 8B fails | Fails | Unknown |
| 145 s jury clip → ≤ 300 s | Holds | Holds | Reported 61–71 s for a 17 s clip at 5 fps on the L4 → **145 s at 5 fps is a risk** [Rep, D] |
| New camera angle | Needs no setup; recognition untested | Needs no setup | **Per-video manual grounding override is unavailable on the jury video (risk)** |

- **Sensitivity point:** object-state perception at the decisive location.
- **Trade-off point:** the verdict rule (FAQ 16, recall first) vs. clean-video false alarms. With chance-level scores, any threshold just moves along the diagonal.

## 11. Planned vs. executed

| Executed | Planned, not run | Blocked / out of scope |
|---|---|---|
| Hardware and VRAM inventory; protocol, split and scorer (verified); 4B smoke and profile; F3 ×2; window verification ×6; proposer recall; F4 ×2; F1 zone-free; A1 (8B); A2 ×2 (dev); B1 ×4; full re-score after the workbook edit | Qwen2.5-VL-7B on the windows (dropped: a third VLM can't change the A1 conclusion); F3/F4 with 8B on full clips (gated on A1 passing; it didn't) | Other-angle footage (needs team filming); the teammate F1 full-run metrics (not read, at the user's request); mechanism-specific detectors trained on locally boxed frames (not built) |

## 12. Remaining risks

1. **Detection quality is at chance for every measured method.** Detection, localization and classification carry 55 of the 100 points.
2. No cross-view evidence.
3. The teammate F1 app is unverified at full scale. It has a manual-calibration dependency and a 5-fps runtime risk on 145 s clips.
4. Small n: Wilson half-widths of about 20 points. Differences of 2 videos or fewer are ties.
5. Annotation reliability: the workbook changed during validation, and 4 of 21 violation clips are excluded from mechanism scoring.

## 13. Incident: private data in a public repository

`https://github.com/Yertugan06/Hackathon` is **public** (GitHub API, checked 2026-10-17). Commit `8155025` ("reasreach 1") tracks and pushed:
- `validation/validation-private/`: GT with workbook text, the local models' frame descriptions, per-clip predictions;
- `data/Таблица_нарушений.xlsx` and `data/Cash_Discipline_Cases_Rules.xlsx`;
- `data/prepared/`.

The same commit changed `.gitignore` from `data/` to `open`. No videos are tracked. FAQ 6 limits the data to hackathon use. **Recommended now:** make the repo private. Then decide whether to purge the history; that needs a force-push, so it's your call.

## 14. Reproduction

Run from the repository root, with the research root `validation` and the venv `/home/yertugan/.venvs/dt26`.

```
python -I validation/validation-evidence/harness/gt.py validation
python -I validation/validation-evidence/harness/split.py validation
python -I validation/validation-evidence/harness/motion.py validation && python -I validation/validation-evidence/harness/propose_eval.py validation
python -I validation/validation-evidence/harness/f3_discovery.py validation {whole_1fps_s288|chunk30_2fps_s288} all
python -I validation/validation-evidence/harness/verify_windows.py validation 4 448 [tag] [v1|items] [all|dev]
python -I validation/validation-evidence/harness/f4_cascade.py validation {motion_short|uniform10} 5
python -I validation/validation-evidence/harness/f1_rules.py validation both cuda
python -I validation/validation-evidence/harness/f2_probe.py validation {dinov2|siglip2} [raw]
python -I validation/validation-evidence/harness/score.py validation <pred> [--split dev|lockbox]
# datathon2: ~/dt26-validation (same layout); VLM_DIR selects the model; queues d2_queue.sh, d2_queue_b.sh
```

## 15. Process notes

- **Agents:**
  - An independent verifier reproduced the protocol.
  - A CV subagent returned unrun code with a broken COCO class list and a placeholder rule. It also made an unrequested local commit; that commit was soft-reset, never pushed. The code was replaced.
  - The prior agent definitions in `archive/agents/` were reused as instructions; no new definitions were added.
- **Downloads:** a rejected local 8B download had started anyway. It was stopped; 7.8 GB of partial files remain in `/home/yertugan/models/Qwen3-VL-8B-Instruct`.
- **Servers:** the shared `datathon` VM was left alone after a teammate's vLLM server filled its GPU. My workspace there (`~/dt26-validation`, incl. 8B weights and GT) is still on disk; I can delete it on request.
