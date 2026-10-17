# ADR-002: Architecture for the cashier-violation service

**Status:** accepted, 2026-10-17 19:30 (+05). Deadline 2026-10-18 12:00, about 16.5 h away.
**Supersedes:** ADR-001 (`solution-decision.md`) on one point. ADR-001 adopted the teammate F1 app as the detector *if* its full run beat the floors. The run is now available. **It failed that check** (§3).
**Companion docs:** `architecture.md` (contracts, budgets, failure plan) and `implementation-plan.md` (work packages, order, go/no-go).

Evidence labels: **[M]** measured by our scripts · **[Rep]** reported in a teammate log, re-scored here with our harness · **[E]** estimate · **[H]** hypothesis.

## 1. Sources compared

| Effort | Location | What it contains | State |
|---|---|---|---|
| **R1: research agent 1** | `archive/research1/problem-validation.md`, `solution-decision.md`, `validation/validation-evidence/` (harness, logs, PREREGISTRATION) | F3 whole-video VLM, F4 cascade, window verification (4B/8B), F2 frozen-feature probes, zone-free COCO rules, proposer recall, anchor probe | Complete, pre-registered, scorer independently verified |
| **R2: team efforts on Brev** | `archive/vm-copies/datathon/` | (a) `forte-model-check-…` = **F1 app** `forte-cash-checker`: OWLv2 + CLIP crop states + RTMPose + ByteTrack, 16 rules, full FastAPI/React service; **full 40-video 5 fps GPU run**. (b) `forte_brev_kit` = **VLM questionnaire**: Qwen3.5-9B FP8 on vLLM fills a per-frame JSON state form; deterministic timeline rules; codex of 217 norms; **full 40-video run** plus gold-frame state checks. (c) `from-datathon2/agentA-rulebook`: F1 app variant with new signals. (d) `agentB-hybrid`: person anchors → crop VLM questions | (a), (b) complete. (c) **partial**: 18 of 24 dev clips. (d) **detection run only, not scored** |

Earlier inputs (problem-reframing, exploration, landscape, data-exploration, senior-ideas, task.md) are summarised in R1 and not repeated. `data/prepared/` covers phases 1–2 only. **No Phase-3 taxonomy or Phase-4 legal-knowledge outputs exist yet.** No per-clip content was read into this context; every comparison below is aggregate.

## 2. Hardware (inspected 19:00)

| Machine | GPU | Free VRAM | CPU / RAM | Disk | Stack | Role |
|---|---|---|---|---|---|---|
| Laptop (WSL2) | RTX 4080 Laptop **12 GB** | 12.0 GB, idle | 8 threads; **10 GB** WSL cap (.wslconfig) | 863 GB free | torch 2.14.1+cu126; Qwen3-VL-4B (8.3 GB), partial 8B | Dev only. Behind NAT, no public URL |
| `datathon2` (Brev) | NVIDIA **L4 23 GB**, dedicated | **22.6 GB, idle** | **4 vCPU, 15 GB RAM** | 219 GB free | torch 2.11.0+cu128; ffmpeg with CUDA hwaccel; Qwen3-VL-4B and 8B on disk | **Production host (decision)** |
| `datathon` (Brev) | NVIDIA L4 23 GB, **shared** (team app, vLLM) | not probed | n/a | n/a | vLLM serving Qwen3.5-9B FP8 (`~/forte_brev_kit/models`, 18 GiB) | Team dev/eval; not the jury host |

Measured model memory:
- Qwen3.5-9B FP8 in vLLM [Rep, server.log]: 11.05 GiB weights and non-torch, 0.55 GiB peak activation, 2.73 GiB KV at `gpu_memory_utilization 0.65` (72,865 tokens). That is about 14.3 GiB, with init taking 225 s in eager mode.
- Qwen3-VL-4B, HF bf16: 10.0 GB peak [M].
- Qwen3-VL-8B, bf16: 18.4 GB peak [M].
- F1 CV stack: 1.65 GiB peak torch allocation, 12.6 s cold load [Rep].

**The 12 GB laptop cannot host the 9B with a usable KV cache**: weights plus non-torch already take 11 GiB.

## 3. One scorer, all candidates

All rows use the R1 scorer on 40 unique videos (21 violation / 19 clean) and 22 labelled events. Logs: `validation/validation-evidence/logs/arch_rescore_teammates.txt`, `arch_rule_sweep.txt`; R1 rows from `problem-validation.md`.

| System | Correct /40 | Recall | Clean false alarms | Top-1 ±3 s | Any event ±3 s | Events/clip | Type: human norm among outputs (n=17) | Worst runtime |
|---|---|---|---|---|---|---|---|---|
| Floor: always "violation" | 21 | 21/21 | 19/19 | 7 (motion peak) | — | 1 | — | — |
| Ref: duration shortcut (LOO) | 25 | — | — | — | — | — | — | — |
| Ref: relative-position prior | — | — | — | **12** | — | 1 | — | — |
| Ref: constant top-3 codes (in-sample) | — | — | — | — | — | — | **13** (top-1: 7) | — |
| F3 Qwen3-VL-4B whole clip [M] | 23 | 8/21 | 4/19 | 0 | — | — | 6 | 149.5 s (4080) |
| F4 uniform → 4B verifier [M] | 20 | 10/21 | 9/19 | 1 | — | — | 4 | 41 s |
| F2 DINOv2 probe, best [M] | 21 | 17/21 | 15/19 | 8 | — | — | — | — |
| **F1 app**, 5 fps, L4 [Rep→M] | 20 | 14/21 | 13/19 | 6 | 10 | 2.4 / 4.1 | **1** | **294.6 s on a 72 s clip** |
| **VLM questionnaire**, Qwen3.5-9B, 1 s step [Rep→M] | 22 | **19/21** | 16/19 | 3 (first in time) | 13 | 3.0 / 3.3 | **10** | **344.2 s on the 142 s clip** (shared GPU) |
| Same, 2 s step (saved states, subsampled) [M] | 22–23 | 19/21 | 15–16/19 | 5 | 13–14 | 2.5 | not computed | ≈172 s [E] |
| Same, rules pruned and tuned on dev → **lockbox** [M] | 8/16 | 6/9 | 5/7 | 1/10 | 3/10 | 1.4 | — | — |
| agentA, partial dev [M] | 10/18 | 6/9 | 5/9 | — | 3/9 (±2 s) | 1.4 | — | 81.6 s |

Window verification (R1, C3): the verifier said "violation" on 8/22 labelled windows vs 4/19 matched twins at 4B, and on 16/22 vs 15/19 at 8B. It does not discriminate.
Person-presence anchors (R1 anchor probe): within ±1 s of 18/22 events, vs 13.7 expected for random placement at the same density. This is weak timing signal, not detection.

**Reading:**
1. **Every system, from three independent efforts, is at chance on the verdict.** Correct counts are 19–23 against a floor of 21, and every confidence interval overlaps.
2. On top-1 localization, no perception system beats the pixel-free prior.
3. On type, no system beats always naming the most frequent norms.
4. **The VLM questionnaire perceives states well at the labelled moments**: 44/56 field checks correct with v1 prompts, 50/56 with v2, 51/56 with v2 plus zoom. But those 32 gold frames are in-sample: v2 was written after seeing v1's errors on the same frames.
5. **Its rules fire at the same rate on twins.** Dev per-rule counts (violation vs clean clips, of 12 each): `door_open` 6 vs 5, `outsider` 3 vs 3, `safe_open` 1 vs 4. So the decisive difference is not captured at 1 fps, 768 px, full frame.
6. Rule pruning chosen on dev did not transfer: lockbox 8/16.
7. Sampling every 2 s instead of 1 s loses nothing on saved states; 3–4 s becomes offset-sensitive (recall 16–19/21).

**Agreement and disagreement.**
- R1 and R2 agree that generic or zero-shot perception does not separate matched twins. They agree that the verdict and citation must come from code and a catalogue, not from VLM text. Every R2 design already does this.
- They disagree on the vehicle: R1/ADR-001 picked object-state CV (the F1 app), R2's kit picked the VLM as a structured perceiver.
- That disagreement rested on assumptions that were untested until now. Both vehicles now have full runs, and the data above decides between them on secondary axes, since neither wins on discrimination.

## 4. Decision

### Primary: VLM state timeline ("questionnaire") inside the existing F1 service shell

**Pipeline:**
- Sample frames over the **whole** video every **2 s**, coarse-first with a deadline (§ architecture 4).
- **Qwen3.5-9B (FP8, vLLM, local)** fills a fixed, schema-constrained state form per frame. It is only a perceiver: it never decides, describes or cites.
- Deterministic temporal rules turn the state timeline into findings.
- Each finding maps one-to-one to a rule in the local **Knowledge Pack**, which supplies the type, the templated description and the verified norm citation.
- Evidence JPEGs are cut from the source video at the finding's anchor.
- All of this runs in the `forte-cash-checker` FastAPI/React shell: API, job store, worker, evidence, UI, Docker and tests already exist and pass. Production runs on **`datathon2` (dedicated L4)**.

Models: **one VLM, Qwen3.5-9B FP8**. Apache-2.0 per the kit's check of the model card on 17.10; re-check before submission. No other model is in the primary path.

**Why this over the alternatives.** Discrimination is a tie at chance, so the choice rests on the axes where the data differ:

| Axis | VLM questionnaire | F1 app | F3 / F4 |
|---|---|---|---|
| Recall (FAQ 16: a miss is unacceptable) | **19/21** | 14/21 | 8–10/21 |
| Type: any output matches the human norm (n=17) | **10** | 1 | 4–6 |
| Any event within ±3 s | **13/22** | 10/22 | — |
| Runtime driver | **Linear in duration; tunable by step** (2 s step measured lossless) | Grows with scene activity: a 72 s clip took 294.6 s, so 145 s is unbounded | Fits |
| Other camera angle (FAQ 4: the final jury video is filmed from another angle) | **No calibration or geometry** | Auto-zones from the first 2 s; manual per-SHA override is impossible on jury videos | No calibration |
| New violation types (FAQ 9) | Add a form field and a rule | Add detector prompts and rule code | Free text, unusable for verdicts |
| Moving parts | 1 model + rules | 4 models + tracker + calibration | 1 model |

**Why not F3 or F4:** falsified on recognition (C2, C3, A1), and the VLM's free text is the hallucination risk that criterion 4 penalises.

**Why not the F1 app's detector:**
- recall 14/21;
- type 1/17;
- runtime not bounded on a 145 s clip;
- most dependent on viewpoint.

**We keep its whole service shell.**

**Why not a richer hybrid now:** crop-zoom re-asks and person-anchor snapping are untested end to end. They stay optional (Phase 4), each gated by a dev → lockbox check.

### Verdict and output policy (product decisions, stated in LIMITATIONS)

- `violation` iff at least one rule finding survives the temporal rules. **No forced verdict and no hidden fallback.** Measured consequence: about 19/21 recall at about 80 % clean false alarms on this data.
- At most **3** violations per video, ranked by rule persistence (WP3 freezes the ranking on dev).
- Descriptions use "признаки возможного нарушения" wording (brief §7).
- Every citation comes from the Knowledge Pack. A norm without human verification is shown as **"источник требует проверки"** and is never presented as confirmed.

### Fallbacks and triggers

| Level | Fallback | Trigger |
|---|---|---|
| L1, same architecture | **Coarse mode**: 4 s step, no refinement. Recall 16–19/21 on saved states, offset-sensitive | 142 s clip warm end-to-end > 240 s at the 2 s step after the prefix-cache fix, or queue pressure (automatic per job) |
| L2, same architecture | **Qwen3-VL-4B** (Apache-2.0, already on `datathon2`), same form via vLLM | 9B not serving on `datathon2` by 01:00; license check fails; OOM |
| L3, other detector | **F1 app detector** at 2–3 fps, same shell, chosen by config (`DETECTOR=f1`) | Questionnaire adapter not returning contract-valid results end to end by 06:00 |
| Floor | Shell returns `failed` with an explicit error, never a fabricated clean verdict | Any unrecoverable error |

### Accepted trade-offs

- We ship a detector that is **not shown to beat chance**, and we say so in the limitations.
- Clean-video false alarms stay high, because we choose recall per FAQ 16.
- A 14–18 GB GPU footprint and a 4–5 min cold start, mitigated by a warm process and a readiness gate.
- A dependency on vLLM.
- The score expectation is honest: the controllable criteria (norms 15, product 10, architecture 10, plus robustness behaviour) get most of the remaining effort.

## 5. Unverified assumptions (must be checked, owner in the plan)

1. 145 s end-to-end within 300 s on `datathon2` at the 2 s step [E: ≈172 s, extrapolated from 2.41 s/frame measured on a *shared* GPU]. **This is the single highest-value experiment** (WP2, by 01:00).
2. Prefix caching of the fixed form prompt cuts prefill. Measured prefix-hit rate was 0.8 %; prefill is about 1,550 of roughly 1,700 tokens per frame [E from the server log throughput].
3. `datathon2` can serve a public HTTPS URL [unverified; WP1, first task].
4. Qwen3.5-9B's license is Apache-2.0 [Rep from the kit; re-check the model card].
5. Behaviour on another camera angle [untested; WP4 films clips].
6. Norm citations: `codex_verified.json` says "verified", but no record of human verification exists. Known conflict: screen lock is cited as `53-71-9` (kit), `48-71-9` (R1 workbook), and "48 п.71 пп.9, repealed; successor to confirm" (F1 app).

## 6. What would change this decision

- A crop-level or zoomed state check that separates labelled windows from matched twins on dev **and** lockbox would add a verification stage (the Phase 4 hybrid).
- The 145 s timing failing even in coarse mode with the 4B model would mean switching to the F1 detector at low fps.
- Nothing else measured so far would justify a different primary.
