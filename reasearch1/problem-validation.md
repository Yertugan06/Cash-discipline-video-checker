# Problem Validation — Datathon 26 (ForteBank)

Status: **in progress, 2026-10-17 ~17:30.** Every measured approach is at chance or no better than the trivial baselines. The one experiment that can still change the direction, a larger VLM on the same windows (A1, plus A2), is staged on the team's Brev L4. It waits for GPU memory held by a teammate's vLLM server. A1 is the decision gate (§9).

Inputs: `task.md`, `problem-reframing.md` (rev 5), `problem-exploration.md`, `data-exploration.md`, `technology-research-landscape.md`, `senior-ideas.md`, `skills/problem-validate/SKILL.md`, the human workbook and `validation-evidence/`.

**Evidence labels:** **[M]** measured in this run (script + log) · **[R]** reproduced independently · **[D]** derived · **[Rep]** reported by others, not reproduced · **[H]** hypothesis.
**Privacy:** all inference ran on team-controlled machines (laptop RTX 4080 12 GB; the Brev L4 VM, where the team had already approved transfer of the clips and workbooks). No frame, video, model description or per-clip annotation was sent to a cloud AI. Scripts print aggregates only; raw model text and per-clip predictions live in `data/validation-private/` (gitignored).

## 1. Inputs, environment, protocol

| Item | Value |
|---|---|
| Laptop | RTX 4080 Laptop 12 GB, WSL 9.7 GB RAM + 4 GB swap, 8 vCPU; torch 2.14.1+cu126, transformers 5.20.1 (`validation-evidence/harness/requirements-lock.txt`) [M] |
| Brev VM `datathon` | NVIDIA L4 23 GB, 15 GB RAM, 4 vCPU, torch 2.11.0+cu128, transformers 5.20.1. Shared: about 4 GB held by a teammate's app and about 14 GB by a teammate's vLLM engine at 17:20 [M] |
| Models | Qwen3-VL-4B-Instruct (Apache-2.0, rev `ebb281ec`, SHA-256 verified); RT-DETR v2 r18 (Apache-2.0, rev `5650961749`). Staged on VM: Qwen3-VL-8B-Instruct (Apache-2.0, rev `0c351dd0`), Qwen2.5-VL-7B-Instruct (cached, Apache-2.0) |
| Annotation workbook | `data/Таблица_нарушений.xlsx`. **`Таблица_нарушений(1).xlsx` does not exist in the project.** The file present is byte-identical to the latest download, `Таблица_нарушений (2).xlsx`. Sheets: Нарушения / Без нарушений / Нормы |
| Ground truth | Organizer labels only, for verdict and time. Human workbook: norm code (mechanism) on the **mechanism-reliable subset (17 of 21 violation videos)**. It excludes X-1, X-11, X-13 and X-44, and rows flagged ОБЯЗАТЕЛЬНО unless re-reviewed (X-24, X-32 re-reviewed). Camera-layout tag from `Cash_Discipline_Cases_Rules.xlsx` (3 layouts) [M] |
| Units & split | 40 unique videos (21 V / 19 C), 22 organizer events. **22 groups**: byte duplicates plus violation/clean pairs from the workbook. Dev 24 (12/12), lockbox 16 (9/7), grouped and layout-stratified, seed 26 [M, R] |
| Pre-registration | `validation-evidence/PREREGISTRATION.md`: claims, falsifiers and decision rules, written before any model output; Addendum A written before A1/A2 |
| Scorer | `harness/score.py`: video confusion with Wilson intervals; per-layout rows; localization within ±1/2/3/5 s under N.0 and N+0.5, any-event and top-1; mechanism agreement on the reliable subset; runtime |
| Independent verification | A separate agent reproduced the GT counts, duplicates, split integrity and scorer outputs on synthetic predictions (`validation-evidence/verify/`) [R]. Its one "inconclusive" item came from a different baseline definition: it used the median absolute time, while the original uses relative position × duration. The original script reproduces 25/40 and 4/9/12/18 exactly [M] |

Human vs. organizer labels: the human event times agree with the organizer seconds within 1 s for **22/22** events [M]. So the workbook adds mechanism and norm code, not independent timing. Human onset/offset annotations do not exist. Localization can only be scored against the integer-second organizer label.

## 2. Compliant baseline and trivial floors

| Floor | Verdict (40) | Top-1 within ±1/2/3/5 s (22 events) | Note |
|---|---|---|---|
| Always "violation" | 21/40 (recall 21/21, clean-FP 19/19) | — | FAQ 16 "no misses" satisfied trivially |
| LOO duration threshold | 25/40 [R] | — | Shortcut; no system may use it |
| Relative-position timecode prior | always violation | 4/9/12/18 (video-LOO) [R]; 3/9/12/17 (group-LOO) [M] | **Shortcut reference** for localization; no system may use it |
| F0: always violation + top motion peak | 21/40 | 4/6/7/9; any of 3 peaks 10/12/15/19 [M] | Compliant floor that uses pixels only |
| F0: motion-threshold verdict (group-LOO) | 14/40 [M] | — | Below chance: motion carries no verdict signal, so motion does not leak a scene shortcut either |

## 3. Candidates screened

| Family | Status | Reason |
|---|---|---|
| **F3** whole-video local VLM | Finalist; measured with 4B | Open vocabulary, no calibration, one code path for unseen types |
| **F4/D** coverage-first cascade (proposer → VLM verifier) | Finalist; measured with 4B | Separates recall from precision; bounded cost |
| **F1** structured CV + temporal rules | Finalist; zone-free probe measured. The teammate's full F1 app (`forte-cash-checker`) is the real contender, results **[Rep]** | Deterministic, explainable, cheap |
| **F0** minimal baseline | Floor | Must be beaten |
| F2 few-shot embedding prototypes | Excluded as decision-maker | About 22 events, duration shortcut, closed set (exploration §5). Not run |
| Novelty / anomaly, end-to-end supervised classifier | Excluded | New-angle false alarms; no impropriety source; few positives |

## 4. Claim register (pre-registered) and outcome

| ID | Claim | Falsifier | Outcome |
|---|---|---|---|
| C1 | 4B VLM loads and processes the longest clip (142.5 s) end to end within the 5-min budget | OOM, or no margin | **Holds [M].** Load 94–127 s (once per service start). Whole clip at 1 fps / 288 px: 11k tokens, prefill 13 s, worst clip end to end 149.5 s, because decode slows to about 0.17 s/token near the 12 GB ceiling. 30 s chunks: worst clip 30.4 s. Feasible, with margin depending on output length |
| C2 | F3 discovers events without timestamps better than the floors | Top-1 ≤ blind prior; recall ≈ FP rate | **Falsified for 4B [M]** (§5) |
| C3 | VLM verifier separates labelled windows from matched hard negatives | Yes-rate on matched twins ≈ positives | **Falsified for 4B [M]** (§6) |
| C4 | Motion proposer keeps events at partial coverage and beats uniform | Motion ≤ uniform at equal coverage | **Weakly holds, low value [M]** (§7). Clips are short, so uniform coverage is nearly as good |
| C5 | Zone-free COCO rules separate violation from clean clips | Rule fire rate on clean ≈ violation | **Falsified [M]** (§8) |
| C6 | Results hold across camera layouts | A layout where a candidate collapses | **Not testable yet**: nothing works on any layout. No cross-view claim is made |
| A1 | A larger VLM (8B; 7B as a second family) raises positive yes-rate without raising false yes | Same discrimination as 4B | **Blocked** (§9): staged, GPU occupied |
| A2 | Per-item yes/no prompt improves 4B/8B verification on dev | No change | **Blocked**, staged after A1 |

## 5. F3: whole-video discovery (no timestamps given) [M]

Frozen prompt `DISCOVERY_V1`: a 13-item checklist written from the public RK norms (NBRK 231, 14, 48; AML law), viewpoint-free, empty list allowed. Qwen3-VL-4B bf16, laptop.

| Config | Verdict all 40 | Dev / lockbox | Top-1 ±3 s | Any-event ±3 s | Median nearest error | Norm code (reliable 17) | Worst runtime |
|---|---|---|---|---|---|---|---|
| Whole clip, 1 fps, 288 px | 23/40: TP 8, FN 13, FP 4, TN 15 | 15/24 · 8/16 | 0/22 | 1/22 | 9.0 s | 6/17 anywhere, 1/17 at ±3 s | 149.5 s |
| 30 s chunks, 2 fps, 288 px | 20/40: TP 9, FN 12, FP 8, TN 11 | 12/24 · 8/16 | 0/22 | 0/22 | 6.5 s | 5/17, 0/17 | 30.4 s |

- Recall of 8–9/21 against the always-violation floor of 21/21 violates FAQ 16's "no missed violation" ordering. Clean-FP of 4–8/19 is not low enough to compensate.
- Localization is **worse than the pixel-free blind prior** (12/22 at ±3 s).
- The timestamp plumbing was checked: the processor emits the true midpoints (`<0.5 seconds>`, `<2.5 seconds>`, …) for 1 fps sampling. The failure is the model's, not the harness's.
- The `_hm` variant (high/medium confidence only) scored identically: the model never labels its events "low".
- The chunked config replaced the pre-registered `chunk30_2fps_s448` after profiling. At 448 px each chunk is about 11k tokens, the memory-bound regime. This is a feasibility change, not tuning.

## 6. Verification on labelled windows (4B) [M]

Frozen prompt `VERIFY_V1`. 8 s windows at 4 fps / 448 px; label ±4 s. Matched hard negatives come from the same staged group: same absolute time in the clean twin.

| Window set | n | Model says "violation" |
|---|---|---|
| Labelled event windows | 22 | **8** |
| Same time, clean twin (matched hard negative) | 19 | 4 |
| Random window, clean clip | 19 | 5 |
| ≥ 10 s away from every label, violation clip | 11 | 2 |

- Norm code correct on 3/5 reliable yes-positives.
- Time error on yes-positives: median 4.0 s (0/8 within ±2 s), which is chance inside an 8 s window.
- Per window: median 7.8 s, peak 10.0 GB.

**Reading:** the 4B model mostly cannot recognize these violations even when shown the right 8 seconds at near-native resolution. **Recognition, not search, is the bottleneck.** This caps both F3 and F4 for this model.

## 7. Proposer recall and F4 cascade [M]

Hit = label second inside a window. Coverage = fraction of the clip inside windows. "short" = peaks of 1 s-smoothed frame difference.

| Proposer | K | ±W | Events covered | Mean coverage (violation clips) |
|---|---|---|---|---|
| short motion | 3 | 2 s | 18/22 | 0.56 |
| uniform | 3 | 2 s | 15/22 | 0.59 |
| short motion | 5 | 2 s | 20/22 | 0.72 |
| uniform | 5 | 2 s | 19/22 | 0.86 |
| short motion | 8 | 2 s | 21/22 | 0.76 |
| uniform | 8 | 3 s | 22/22 | 0.96 |

- Motion peaks beat uniform placement at equal K. But the violation clips are short (median 20 s), so 20/22 already needs about 70 % coverage.
- **On these clips the proposer saves little.** It only matters for long clips (the jury's limit is 145 s), where its value is unmeasured.
- Motion compute: 38 s CPU for all 21.6 min of footage; worst clip 5 s.

F4 = top-5 proposals → 8 s windows → `VERIFY_V1` (4B):

| F4 variant | Verdict | Top-1 ±3 s | Worst runtime |
|---|---|---|---|
| Motion proposals | 20/40: TP 8, FN 13, FP 7, TN 12 | 1/22 | 44.1 s |
| Uniform proposals | finishing on the laptop; to be appended | — | — |

As predicted by §6, the cascade inherits the verifier's failure.

## 8. F1: structured CV + temporal rules [M] and teammate evidence [Rep]

Zone-free probe (`harness/f1_rules.py`): RT-DETR v2 COCO at 2 fps, no manual zones, four pre-registered rules.

| Rule | Fired on violation / clean clips |
|---|---|
| R-bag (231-12-1) | 15/21 vs 14/19 |
| R-phone (231-12-2) | 5/21 vs 5/19 |
| R-leave (231-22) | 9/21 vs 9/19 |
| R-laptop (48-71-9) | 19/21 vs 18/19 |

- Verdict: always "violation" (21/40). Top-1 ±3 s: 5/22. Norm code 2/17.
- CPU runtime: worst clip 113 s.
- **Generic object presence carries no violation signal.** It is all background (bags, monitors, people coming and going).

**Teammate's full F1 app [Rep]**, from its `LIMITATIONS.md`: RT-DETR + OWLv2 + CLIP crop states + RTMPose + ByteTrack, 16 rules.
- Its authors report detection "experimental and currently poor".
- Small checks: 6-clip CPU run at 33 % accuracy; temporal hits with the wrong rule type; X-26 cash miss.
- A full 40-video GPU run was in progress; its result is not reproduced here.
- **Camera-specific assumption:** the app supports a per-video manual override of the automatic desk/safe/door grounding. The jury's new-angle video cannot get one, so any accuracy that depends on it does not transfer.

## 9. Blocked / pending experiments (exactly what is missing)

| Exp | What | State | Blocker |
|---|---|---|---|
| A1 | Qwen3-VL-8B (int8; vision tower bf16) on the same §6 windows, same prompt | Weights downloaded to VM and SHA-256 verified; queue `vm_queue1.sh` armed | Needs ≥13 GB free VRAM. Teammate vLLM engine (~14 GB) + app (~4 GB) leave ~4 GB |
| A1b | Qwen2.5-VL-7B (int8, cached) on the same windows | Queued after A1 | Same |
| A1c | Qwen3-VL-4B on the L4 (cross-machine reproduction of §6) | Queued | Same |
| A2 | Per-item yes/no prompt (`VERIFY_ITEMS_V2`), 4B and 8B, dev split | Queued (`vm_queue2.sh`) | Same |
| F3/F4 with the best A1 model | Full 40 clips, if A1 shows discrimination | Not yet queued | Conditional on A1 |
| Lockbox scoring of any tuned prompt | Once, after dev | — | Conditional on A2 |
| Cross-view (new angle) | Own re-staged other-angle footage (data-exploration §D.B) | **Not done** | Requires team filming. **No cross-view robustness claim is made anywhere** |
| Teammate F1 full-run metrics | Aggregate verdict and localization | Not read (user asked me not to probe) | Ask the teammate for the aggregate numbers |

## 10. Comparison (current evidence)

Ranked by the pre-registered order: recall, then clean-FP, then top-1 localization vs. the blind prior, then mechanism, then runtime.

| Candidate | Recall | Clean-FP | Top-1 ±3 s | Mechanism (17) | Worst runtime | vs. floors |
|---|---|---|---|---|---|---|
| Always violation + motion peak (F0) | 21/21 | 19/19 | 7/22 | 0 | ~5 s | Floor |
| F1 zone-free COCO rules | 21/21 | 19/19 | 5/22 | 2 | 113 s CPU | = floor |
| F3 whole, 4B | 8/21 | 4/19 | 0/22 | 1 at ±3 s | 149.5 s | **Below floor on recall and localization** |
| F3 chunked, 4B | 9/21 | 8/19 | 0/22 | 0 | 30 s | Below floor |
| F4 motion → 4B verifier | 8/21 | 7/19 | 1/22 | 2 | 44 s | Below floor |
| Blind position prior (shortcut, reference) | 21/21 | 19/19 | 12/22 | — | 0 | Best localization, but forbidden |

**Measured conclusion:** with Qwen3-VL-4B or generic COCO rules, no approach discriminates violation from clean videos or localizes better than a pixel-free prior. The F3 vs. F4 vs. F1 ranking is **undetermined by the evidence so far**: all are at chance. Their differences are within ±2 videos, a tie under the pre-registered rule. Runtime is not the binding constraint: every configuration fits within 5 minutes.

## 11. ATAM-lite scenarios

| Scenario (stimulus → condition → response) | F3 | F4 | F1 (zone-free) |
|---|---|---|---|
| Cash left on the desk, 20 s clip, overhead → must flag within ±3 s | Risk: recognition fails (§6) | Same verifier risk; proposer fine | Risk: no "cash" or "desk" without grounding; generic objects fire everywhere |
| Clean twin with identical staging → must stay silent | 4/19 false yes on matched twins | Same | Fires on all clean clips |
| 145 s jury clip → ≤ 300 s | Holds (149.5 s worst; token-bound) | Holds (bounded windows) | Holds (113 s CPU; GPU faster) |
| New camera angle → same behaviour | Untested; no calibration needed (non-risk for setup) | Untested; proposer is zone-free | Zone-free probe: no setup. **Teammate app: manual override is unavailable on the jury video (risk)** |

- **Sensitivity point:** recognition quality of the perception model, shared by F3, F4 and the VLM half of any hybrid.
- **Trade-off point:** recall vs. FP is set by the verdict rule, and no current scorer separates the classes, so any threshold just trades one for the other.

## 12. Remaining risks

1. **Perception is the bottleneck.** Small cash and hand actions at 464×848 (exploration N3) may be beyond any zero-shot model at this size. A1 is the cheapest test.
2. The decisive mechanism is concentrated: norm 231-20-2 ("only the current client's cash on the workplace") is 8 of 22 labelled events. A targeted detector for that state (cash on the desk while unattended) is the strongest untested direction if A1 fails. It is data-limited (data-exploration §8, strategy C gate) [H].
3. No cross-view evidence exists. The only way to get it is own re-staged footage.
4. The shared GPU on the VM: the demo service, a teammate's vLLM server and experiments compete for 23 GB. The deployment needs a resource plan.
5. Small n: Wilson intervals of about ±20 points. Decide only on large differences.

## 13. Recommendation (provisional)

**Decision: defer the architecture choice to the A1 gate; build the compliant end-to-end service now.**
- The mandatory flow is independent of the detector: upload → job → verdict JSON → evidence frames → rule citation from the verified Нормы catalog. Build it with a pluggable detector.
- Do not invest further in F4's proposer, whole-video prompting or zone-free COCO rules. None beat the floor, and the bottleneck is upstream of all three.

**Switching conditions (pre-registered):**
- **A1 favours a larger VLM:** positive yes-rate clearly above both negative sets, by at least 3–4 windows. Then run F3 chunked and F4 with that model on all 40 clips, then the lockbox. Prefer F4 if F3's localization stays below the blind prior. Its windows give the time; the model gives the type and description.
- **A1 shows the same failure:** the VLM is limited to describing evidence frames. Detection must come from mechanism-specific perception: the teammate's F1 app or a targeted 231-20-2 detector. Its full-run aggregate metrics are then the deciding evidence and should be requested from the teammate.
- **In either case,** an honest product states its limits (brief §8). The verdict policy under FAQ 16 must be chosen explicitly, not tuned on these 40 clips.

## 14. Reproduction

```
# laptop (GPU venv /home/yertugan/.venvs/dt26)
python -I validation-evidence/harness/gt.py .        # private GT, aggregates printed
python -I validation-evidence/harness/split.py .
python -I validation-evidence/harness/motion.py . && python -I validation-evidence/harness/propose_eval.py .
python -I validation-evidence/harness/f3_discovery.py . whole_1fps_s288 all
python -I validation-evidence/harness/f3_discovery.py . chunk30_2fps_s288 all
python -I validation-evidence/harness/verify_windows.py . 4 448
python -I validation-evidence/harness/f4_cascade.py . motion_short 5
python -I validation-evidence/harness/f1_rules.py . both cuda
python -I validation-evidence/harness/score.py . <pred_name> [--split dev|lockbox]
# Brev VM (~/dt26-validation, .venv): validation-evidence/harness/vm_queue1.sh, vm_queue2.sh
```

Logs for every number above: `validation-evidence/logs/`.

## 15. Process notes

- **Subagents:** an independent verifier reproduced the protocol (kept). A CV subagent produced unrun code with a wrong COCO class list and a placeholder rule that fired on everything. It also made an unrequested local git commit. The commit was soft-reset (never pushed) and its files were moved out of the repo. F1 was reimplemented and run by the coordinator.
- **Download incident:** a rejected local 8B download had in fact started. It was stopped; 7.8 GB of partial files remain in `/home/yertugan/models/Qwen3-VL-8B-Instruct`.
