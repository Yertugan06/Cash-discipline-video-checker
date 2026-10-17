# Pre-registration — problem validation (written 2026-10-17 ~15:30, before any model output)

Only absolute threshold: the brief's 5-minute limit per video (FAQ 14). Everything else is comparative:
a candidate must beat the baselines and its rivals on the same clips, under the same scorer.

## Protocol (frozen)
- Unit = unique video (40). Groups = byte duplicates + violation/clean pairs from the human workbook (22 groups).
- Split: dev 24 (12 V / 12 C), lockbox 16 (9 V / 7 C), grouped, stratified by camera layout, seed 26 (`harness/split.py`).
- Ground truth for verdict and time: organizer labels only. Human workbook: norm code (mechanism) on the
  "mechanism-reliable" subset only (excludes X-1, X-11, X-13, X-44 and rows flagged ОБЯЗАТЕЛЬНО unless re-reviewed).
- Scorer: `harness/score.py` (independently verified on synthetic predictions, `validation-evidence/verify/`).
- Baselines every candidate must beat: always-violation (21/40), LOO duration threshold (25/40),
  relative-position timecode prior (±1/2/3/5 s: 4/9/12/18 of 22, REFERENCE ONLY — a shortcut no system may use).
- Prompts frozen in `harness/prompts.py` (catalog from public RK norms). Any prompt change after seeing outputs is
  tuned on dev only and reported as such; lockbox scored once per frozen config.
- Cross-view: leave-one-layout-out style reporting (3 layouts in the dataset). This is cross-*layout* within the
  organizers' camera style, not evidence for the jury's new angle.

## Claims, falsifiers, consequences
| ID | Claim | Falsified if | Consequence if false |
|---|---|---|---|
| C1 | A local VLM (Qwen3-VL-4B, Apache-2.0) loads and processes the longest clip (142.5 s) end-to-end on this laptop GPU | OOM, or worst-case wall time leaves no margin under 300 s once decode + evidence frames are added | F3 dropped at that config; F4 bounded-window becomes the only VLM path |
| C2 | F3 discovers events without timestamps: video recall above always-violation's precision trade-off, i.e. recall high AND clean-FP below 19/19, and top-1 localization beats the blind prior | top-1 hit rate ≤ blind prior at ±2/±3 s, or recall ≈ FP rate (no discrimination) | VLM is not a discoverer; at most a verifier/describer |
| C3 | The VLM verifier discriminates labelled windows from matched hard negatives (same scenario, same time, clean twin) | yes-rate on pair_neg ≈ yes-rate on pos | verifier adds no precision; F4 loses its rationale |
| C4 | A cheap motion proposer keeps labelled events at partial coverage and beats uniform placement at equal coverage | motion ≤ uniform at equal coverage, or ≥20/22 needs ~full coverage | F4's proposer stage is pointless → dense coverage (= F3 chunked) |
| C5 | F1 (COCO detector + zone-free temporal rules) separates violation from clean clips | per-rule fire rate on clean ≈ on violation | F1 only as auxiliary evidence |
| C6 | Results hold across camera layouts | a layout where a candidate collapses | no robustness claim beyond layouts measured; new-angle remains untested |

## Decision rules
- Rank by: (1) violation-video recall (FAQ 16 lexicographic reading), (2) clean-video FP, (3) top-1 localization vs blind prior, (4) mechanism agreement on the reliable subset, (5) worst-case runtime ≤ 300 s.
- Differences of ≤ 2 videos are treated as ties (n = 21/19; Wilson intervals ±20 pts).
- A hybrid is preferred only if it beats both parents on (1)–(2) or matches them at lower runtime/risk.

## Addendum A (2026-10-17 ~16:25, after F3-whole and the 4B verification probe; before running either test below)
Trigger: Qwen3-VL-4B said "yes" on 8/22 labelled windows vs 4/19 matched clean twins and 5/19 random clean windows.
Recognition, not search, is the bottleneck. Two decision-changing follow-ups:
- **A1 capacity (one extra model, explicitly required):** Qwen3-VL-8B-Instruct (Apache-2.0, rev 0c351dd01e) loaded in 4-bit NF4
  (bitsandbytes), same windows, same VERIFY_V1 prompt, same scoring. Favours "VLM viable with a bigger model" if pos yes-rate
  rises while pair_neg/rand_neg stay at or below the 4B rates; otherwise the 4B result is not a capacity artefact.
  The 8B-FP8 build (10.6 GB) is excluded: no activation headroom on a 12 GB GPU.
- **A2 focused prompts (dev split only, then lockbox once):** one short yes/no question per catalog mechanism instead of the
  13-item checklist. Same windows; reported separately as a tuned variant.

## Addendum B (2026-10-17 ~18:45, after A1; before any probe is run)
A1 result: Qwen3-VL-8B (bf16, L4) said "yes" on 16/22 labelled windows, 15/19 matched twins, 14/19 random clean, 8/11
off-event windows. Zero-shot VLMs (4B, 8B) do not recognize the mechanisms. This meets the data-exploration §8 gate
for targeted adaptation (DX5): humans judge most events with high confidence; zero-shot fails consistently; norm 231-20-2
recurs in 8 of 22 events.
- **B1 frozen-encoder linear probe (F2 as detector).** Encoders: DINOv2-base (primary, Apache-2.0, rev f9e44c81),
  SigLIP2-base-patch16-384 (secondary, Apache-2.0, rev f775b65a). Frames at 2 fps (PTS); two square crops (top/bottom
  of the portrait frame); per-clip mean-centred features (removes static scene/actor appearance); window = mean over
  ±2 s. Positives: organizer label windows. Negatives: every 2 s of clean clips and violation-clip windows ≥6 s from
  labels. Logistic regression (C=1, balanced, standardized), **leave-one-group-out over the 22 groups** (matched twins
  are always held out together), no tuning.
- Metrics: window AUC pos vs matched-twin windows; video AUC of max window score (violation vs clean); top-1 localization
  at ±1/2/3/5 s vs blind prior 3/9/12/17; verdict with a cross-fitted threshold (balanced accuracy on other groups'
  out-of-fold scores). Shortcut references: duration AUC; same probe without centring.
- Favours "learnable signal" if matched-twin AUC and video AUC are clearly above 0.5 (≥0.70) and top-1 localization beats
  the blind prior. Otherwise the signal is not recoverable from these 40 clips with generic features.
