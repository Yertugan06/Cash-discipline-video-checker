# Implementation plan (ADR-002)

Start 2026-10-17 19:30 (+05). Deadline 2026-10-18 12:00. Team of 4. Architecture: `architecture.md`. Decision: `architecture-decision.md`.

## 0. Kickoff (19:30–20:00, everyone, before any parallel work)

1. **Base code.** Import the latest `forte-cash-checker` from its owner, from `datathon:~/forte-cash-checker`, **not** the `reasearch2/` snapshot. It goes into this repo (`backend/`, `frontend/`, `config/`, `scripts/`, `tests/`, Docker files). The repo's `backend/` and `frontend/` are empty today.
2. **Freeze `backend/contracts.py`** (architecture §2) and the canonical rule-ID mapping (architecture §3). After this point, changes need a message to all owners.
3. **Do not commit `reasearch2/`.** It holds a copied `.env` with an API key, `results.json` with base64 frames of organizer video, and HTML reports. The repo is public, and private data already leaked in `8155025`. Add `reasearch2/` to `.gitignore` and make the repo private.
4. Agree the gates and the sleep rotation (§3).

## 1. Work packages (one owner per file set)

### WP1: Platform, API and deployment (Dev A, ideally the author of `forte-cash-checker`)

- **Objective:** a public, reliable service with the jury contract, a job queue, the deadline, evidence frames, and the `Detector` seam with two implementations wired in (`vlm` and `f1`).
- **Depends on:** contracts (kickoff). WP2 and WP3 deliver modules into the seam.
- **Files:**
  - `backend/main.py`, `config.py`, `store.py`, `worker.py`, `pipeline.py`, `contracts.py`, `evidence.py`, `serialize.py`;
  - `backend/f1/` (the existing perception, events, rules and calibration modules, wrapped as `F1Detector`);
  - `deploy/` (compose, reverse proxy, app systemd unit);
  - `scripts/jury_client.py`, `tests/test_api*.py`.
- **Interface:** `Detector.detect(video, info, plan) -> DetectionResult`; `Knowledge.ground(findings) -> list[GroundedFinding]` (from WP3); output `DoneJob`.
- **Definition of done:**
  - public HTTPS URL on `datathon2`;
  - `/healthz` and `/readyz`;
  - per-job deadline (upload time + 270 s) passed to the plan;
  - uploads and frames deleted after each job, results purged after 24 h;
  - `DETECTOR=vlm|f1` switch;
  - API key only in `.env`.
- **Integration tests:**
  - 401 without a key or with a wrong key; 415 for non-MOV; 413 for oversize; 422 for empty;
  - corrupt MOV → `failed` with a message;
  - POST → 202 → `processing` → `done`, validated against the jury JSON schema;
  - a restart re-enqueues pending jobs;
  - `scripts/jury_client.py` run from the laptop (outside the VM) against the public URL.

### WP2: Perception, VLM questionnaire (Dev B, ML; owner of the brev kit)

- **Objective:** `VlmDetector`, which turns a whole video into a `StateTimeline` within the deadline, then runs WP3's rules to produce a `DetectionResult`.
- **Depends on:** contracts; WP3's `rules.evaluate(timeline, rule_entries) -> list[Finding]`; `datathon2` GPU.
- **Files:**
  - `backend/vlm/` (`sampler.py`, `client.py`, `form_schema.json`, `prompts/`, `detector.py`);
  - `deploy/vllm/` (`serve.sh`, `vllm.service`, pinned `requirements-vllm.txt`);
  - `scripts/bench_vlm.py`, `tests/test_vlm_*.py`.
- **Interface:** `VlmDetector(settings).detect(...)`. The sampler implements the coarse-first plan (4 s grid, then 2 s fill), the running mean of seconds per frame, and the stop at deadline − 15 s. The client sends text first and the image last, so the form prompt is prefix-cached. Each answer is checked against the schema, retried once, then marked `ok=False`.
- **Steps:**
  1. Copy the Qwen3.5-9B checkpoint from `datathon` to `datathon2` (18 GiB, VM to VM). Re-download from HF only if the copy is impossible.
  2. Pin the vLLM version used on `datathon`.
  3. Serve with util 0.80, prefix caching on and CUDA graphs on.
  4. Benchmark.
- **Definition of done:**
  - gate G1 passed;
  - ≥ 99 % schema-valid answers;
  - the deadline test passes;
  - nothing but vLLM on the GPU.
- **Integration tests:**
  - `bench_vlm.py` on the 142 s clip, warm: wall time, frames done, peak VRAM (`nvidia-smi`);
  - forced 60 s deadline → `partial` result returned in under 60 s;
  - vLLM stopped → explicit job failure.

### WP3: Temporal rules, Knowledge Pack and evaluation (Dev C, rules and legal)

- **Objective:**
  - the one authoritative implementation of every rule;
  - the runtime Knowledge Pack with human-verified citations;
  - the frozen-configuration evaluation.
- **Depends on:** contracts. It does not need the GPU: rules develop against the **saved 1 s states** in `forte_brev_kit/brev_kit/runs/q35_9b_fp8/states` (run only on team machines; the content stays private).
- **Files:**
  - `backend/rules/` (`timeline.py`, a typed port of the kit's `timeline_rules.py`, and `ranking.py`);
  - `backend/knowledge.py`;
  - `knowledge/` (`rules.yaml`, `norms.json`, `README.md`);
  - `scripts/build_knowledge.py`, `eval/run_eval.py` (adapter to the R1 scorer);
  - `tests/test_rules*.py`, `tests/test_knowledge.py`, `tests/test_no_label_access.py`.
- **Interface:** `rules.evaluate(timeline: StateTimeline, rules: list[RuleEntry]) -> list[Finding]`; `Knowledge.load(path)` and `Knowledge.ground(findings) -> list[GroundedFinding]`.
- **Definition of done:**
  - ported rules reproduce the kit's output on the saved states (22/40, recall 19/21, any ±3 s 13/22);
  - the ranking (persistence first, then rule order) is chosen on **dev only**, frozen, and scored once on lockbox;
  - every enabled rule has at least one norm;
  - every norm's quote, punkt and URL is checked by a human on adilet.zan.kz, `human_verified` is set, and the 53/48-71-9 conflict is resolved;
  - `docs/RULES.md` is generated from `knowledge/`.
- **Integration tests:**
  - kit fixtures: cash left and unlocked laptop, each with its clean counterpart;
  - an unknown `rule_id` or norm makes the loader fail;
  - no backend module references `data/`, label files or `.xlsx`;
  - `eval/run_eval.py` on API outputs for all 40 videos gives the R1 scorer aggregates.

### WP4: Frontend, robustness, docs and acceptance (Dev D, product and QA)

- **Objective:** a clear UI, an other-angle robustness check, the submission documents, and the external acceptance run.
- **Depends on:** the `DoneJob` contract; WP1's public URL.
- **Files:** `frontend/`; `docs/` (`LIMITATIONS.md`, `ARCHITECTURE_SUMMARY.md`, `USAGE.md`, violation types list); `tests/e2e/`; `robustness/README.md`. Clips are never committed.
- **UI requirements:**
  - both verdict texts from brief §4;
  - per violation: type, timecode, description, 1–3 frames, and the **norm block** (act, punkt, quote, adilet link, `citation_status` badge);
  - a coverage or partial warning;
  - the processing state;
  - the API key entered by the user and kept only in memory.
- **Robustness:** film 10–20 short clips on 2 phones from a **different angle** with matched violation/clean pairs, for the top mechanisms: cash left on the desk, door, keys, unlocked screen. Run them through the public API and report the aggregates as **"tested on N self-filmed clips"**. If time runs out, state "untested on other angles".
- **Definition of done:**
  - `npm test` and the build pass;
  - the docs cover brief §8 (URL, key handover, usage, architecture, models and licences, sources, how rules map to video, types list, limitations and known errors);
  - the e2e suite passes from an external network.
- **Integration tests:** upload 3 clips (short, 142 s, other angle) through the public UI and API. All must be `done` in under 300 s, with valid JPEGs and rendered norms.

## 2. Implementation order

| Phase | Window | Content | Exit gate |
|---|---|---|---|
| **1. Minimal end-to-end product** | 20:00–23:30 | WP1: shell imported and deployed on `datathon2` with `DETECTOR=f1` at 2 fps (real models, the measured fallback) and a public URL. WP3: Knowledge Pack v0 (mapping, norms subset, unverified flags) and rules port with tests. WP4: UI norm block, docs skeleton. WP2: weights copied, vLLM serving, first benchmark | **G0, 21:30:** the jury `curl` works from outside on the public URL and returns a contract-valid `done` |
| **2. Primary model integration** | 22:00–03:30 | WP2 `VlmDetector` + WP3 rules + WP1 grounding and evidence wired through the seam. Deadline-aware sampler | **G1, 01:00:** 142 s clip warm ≤ 240 s at the 2 s plan (else coarse default; > 270 s coarse → L2 4B). **G2, 03:30:** all 40 videos through the API: 0 failures, all < 300 s, contract-valid |
| **3. Quality** | 03:30–09:30 | WP3 ranking frozen on dev, scored once on lockbox; human citation verification. WP2 performance levers in architecture §6 order. WP4 other-angle clips, UI polish, docs. WP1 uptime probe, cleanup, restart drills | **G3, 06:00:** last detector decision (VLM vs F1) on G2 numbers. After this, no detector switch except an emergency |
| **4. Optional** (only if G3 passed by 08:00) | ≤ 09:30 | (a) Crop re-ask of `desk_cash`, `key_in_safe_lock` and `laptop_screen` on desk/safe/laptop crops, at candidate findings only. Adopt only if dev **and** lockbox improve over the frozen config. (b) Snap timecodes to person-presence anchors (R1 probe: ±1 s 18/22 vs 13.7 random). Same gate | Pre-registered: no lockbox look before freezing on dev |
| **Freeze and submit** | 09:30–12:00 | 09:30 code freeze. 10:00 redeploy from a clean checkout and run the e2e suite from an external network. 11:00 submission package (URL, API key, docs). 12:00 deadline | **G4** checklist (§4) all green |

**Critical path:** public URL on `datathon2` → 9B serving on `datathon2` → `VlmDetector` through the seam → G1 timing → G2 full-set API run → frozen config → final external e2e. Everything else (knowledge verification, UI, docs, robustness clips) runs in parallel off this path.

**Estimates (person-hours):**
- WP1: 6–7 h (shell exists; the work is deployment, deadline and seam);
- WP2: 7–8 h (weights copy, serving, sampler, tuning);
- WP3: 6–7 h (port and tests 3 h, knowledge and verification 3 h, eval 1 h);
- WP4: 6–7 h (UI 2 h, filming and run 2 h, docs 2–3 h).

That is about 26 h of work across 4 people in 14 working hours, which leaves room for a sleep rotation: A and C sleep 03:30–07:00, B and D sleep 06:00–09:00. The G2 run happens while B is awake.

## 3. What can start right now (no dependencies)

- WP1: check public port exposure on `datathon2`; import the shell; deploy with `DETECTOR=f1`.
- WP2: copy the Qwen3.5-9B checkpoint to `datathon2`; install the pinned vLLM; serve; benchmark the 142 s clip with the existing `run_vlm.py` at step 2.0 (that gives G1 numbers before the detector is integrated).
- WP3: port `timeline_rules.py` to `backend/rules/` with an equivalence test on the saved states; draft `knowledge/` from `codex_verified.json` and `codex.yaml`.
- WP4: film other-angle clips (needs only phones and a desk setup); UI norm block against a sample `DoneJob` JSON fixture taken from the contract (not from organizer video).

## 4. Final go/no-go checklist (G4, 10:00–11:00)

| # | Item | Pass condition |
|---|---|---|
| 1 | Detection (25) | Frozen config; all 40 training videos and the self-filmed clips through the **public API**; aggregates recorded. Verdict policy (recall first) stated in LIMITATIONS |
| 2 | Localization (15) | Every violation has `timecode_sec` and 1–3 decodable JPEGs at or next to it; frames cut from the source video |
| 3 | Classification (15) | Every `type` comes from a `rules.yaml` title. No free-text types |
| 4 | Normative justification (15) | Every displayed norm has `human_verified=true`, or carries the visible "требует проверки" badge. No citation exists outside `knowledge/norms.json`. The 53/48-71-9 conflict is resolved |
| 5 | Robustness (10) | Other-angle result reported honestly ("N clips, X/Y"), or "untested" stated |
| 6 | Product readiness (10) | Upload → status → result works in the UI from an external network; failed jobs show a reason; the 142 s clip finishes in under 300 s while warm |
| 7 | Technical architecture (10) | Architecture summary, models and licences, locality statement, and limitations published in `docs/` |
| 8 | API compatibility | Jury `curl` from task.md works verbatim; the JSON validates; no required field added; 401 on a bad key |
| 9 | Locality | vLLM bound to loopback; offline env vars set; container or VM egress not needed for processing (verified by blocking egress during one run) |
| 10 | Licences | Model cards re-checked: Qwen3.5-9B (or the fallback model), and the F1 models if used. No AGPL or research-only weights |
| 11 | Hardware fit | Peak VRAM recorded during the G2 run, ≥ 2 GB headroom; no other process on the GPU |
| 12 | Deployment | `restart` policies on; readiness gate on; uptime probe on; budget covers keeping `datathon2` up through jury evaluation and pitching; API key handed over separately |
| 13 | Privacy | No organizer video, frames, results or `.env` in git; repo private; data deletion planned after the event (FAQ 6) |
