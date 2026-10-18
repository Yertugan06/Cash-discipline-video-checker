# Forte cash-discipline video checker

A fully local AI service for Datathon 26 (ForteBank). Upload a short video of a cashier's desk
(`.mov`, `.mp4` or `.mkv`, up to 180 s) and get back a verdict:

- **«Нарушение не обнаружено»** - no violation found, or
- **«Обнаружены признаки возможных нарушений»** - signs of possible violations.

For each finding the service gives the violation type, a timecode, 1-3 evidence frames cut from
the original video with the triggering object boxed, a plain-language description of what is
visible, and the norm of Kazakhstan law it rests on.

No cloud AI is used anywhere in the processing path (task.md §7). Perception, rules, evidence
extraction and serving all run on the team's own GPU host from pre-downloaded, pinned weights.

## Existing public deployment (A20)

| Item | Value |
| --- | --- |
| Web UI | https://forte-checker-wwi4jcrss.gobrev.dev/ (last recorded A20 deployment on `datathon`; see `deploy/README.md`) |
| API base URL | https://forte-checker-wwi4jcrss.gobrev.dev/api/v1 |
| API key | Handed to the jury out of band, never stored in this repo |
| Deployed | commit `277ac67`, `DETECTOR=f1`, `RULE_SCOPE=detector` (see [Legal grounding](#legal-grounding)) |

**For the jury:**

1. Open the Web UI and paste the API key. The key is kept only in the page's memory, never in
   storage or the URL, so you need to enter it again after a reload.
2. Choose a video and submit. The page shows a processing state and polls until the job is done
   (the job budget is 270 s, inside the jury's 300 s limit).
3. The result shows the verdict, then each violation with its timecode, frames, description and
   norm block. The **«Пример (демо-данные)»** button shows the result layout on synthetic data
   without uploading anything.

## Current state — A21

The validated review service runs entirely on **datathon2**, with F1 perception/rules and
local **Qwen3-VL-4B safe-state checks enabled**. It is separate from the existing public
A20 endpoint above. The two-VM split was temporary evaluation only.

- [Evaluation](http://localhost:8103/evaluation), [live results](http://localhost:8103/),
  [watch and annotate](http://localhost:8103/annotate). These URLs require the SSH tunnel
  described in [realtime setup](realtime/README.md#current-one-vm-review-service).
- **42/42 API jobs successful; 30/40 unique verdicts agree with organizer labels**:
  11/21 violations caught, 10 missed, 0/19 clean false alarms.
- Findings: 9 compatible with supplied human observations, 0 contradicted, 3 unknown.
  This is observation compatibility, not legal verification.
- A20 scored 32/40; two of its findings had contradicted explanations. A21 removes those
  accusations and misses the corresponding clips. **Detection accuracy regressed; the
  enabled VLM has not improved the score.**
- The enabled run made 40 fresh VLM calls and reused 476 prior answers. Its median
  2.0675 s is predominantly cached work; a forced-cold X20 took 50.669 s. Longest-clip
  cold latency with the current VLM-enabled configuration has not been measured.
- All 40 public clips influenced development; unseen-room/camera performance is untested.
- All citations remain pending human verification. Use `RULE_SCOPE=detector` for review;
  the default `jury` scope refuses startup while no rule is eligible.

Exact source hashes, validation, known gaps and the preserved comparisons:
[A21 results](attempts/A21-deadline/RESULTS.md).

The same flow through the API is in [API usage](#api-usage).

## Features

- **Verdict + findings** in the exact jury contract (task.md §10), at most 3 findings per video,
  ranked so the top timecode is the clearest moment.
- **15 violation types detected**, in five groups:

  | Group | Rule IDs |
  | --- | --- |
  | Cashier leaves the desk | `L-NO-CASH-ON-LEAVE`, `L-NO-DOCS-ON-LEAVE`, `L-PC-LOCKED` |
  | Safe and cash on the desk | `S-SAFE-CLOSED`, `S-CLEAN-DESK-HANDOVER`, `S-NO-MERGE` |
  | Access to the cash room | `A-OUTSIDER-ZONE`, `A-DOOR-LOCK`, `A-SECOND-PERSON` |
  | Serving a client | `C-COUNT-BEFORE-EXIT`, `C-ID-BEFORE-CASH` |
  | Workplace and cash collection | `W-NO-PERSONAL-ITEMS`, `W-NO-FOOD`, `K-SEAL-CHECK`, `K-RECOUNT-BEFORE-SAFE` |

  Russian names and norms for each: [`docs/VIOLATION_TYPES.md`](docs/VIOLATION_TYPES.md). Seven
  more rules are catalogued but not reported (no evaluator, the legal/visual basis needs review,
  or not yet seen on a clip); they are listed there under "Not detected".
- **Evidence frames** taken from the original video at the finding's anchor time, not from the
  detector's downscaled frames, with the triggering object's box drawn.
- **Norm block per finding**: the description ends with `Основание: <document>, <punkt>` for the
  primary norm; the UI also shows the act, clause, verbatim quote, link, and citation status
  (`verified` / `pending` / `invalid`) as a separate badge.
- **Honest coverage**: if the time budget runs out or calibration is unsure, the response carries
  `coverage.deadline_hit` and a visible warning instead of a silent «no violation». A job that
  fails returns `failed` with a readable error, never a fabricated verdict.
- **Per-job trace** (`GET /api/v1/jobs/{job_id}/trace`): calibration, events, roles, every rule
  finding and per-frame boxes, for debugging a verdict.
- **Live verdict gateway** (`realtime/`, optional): runs a folder of videos through the API one by
  one and streams verdicts over a WebSocket, with side-by-side run comparison and a blind
  annotation page.

## How it works

No model decides the verdict. Pretrained detectors only report what is in each frame; a
deterministic event builder turns that into a timeline, and plain-Python rules turn the timeline
into findings.

```
POST /api/v1/analyze --> job queue (one GPU job at a time, FIFO, 270 s budget)
        |
   ffprobe + ffmpeg: frames at 2 fps
        |
   perception        RT-DETR (people), OWLv2 (desk, laptop, safe, door, cash, documents, bags...),
                     OpenCLIP (door / safe / screen states), RTMPose (hands), ByteTrack (tracks)
        |
   calibration       desk, laptop, safe, door zones from the first 2 s; the cashier's side is
                     where a lone person works at the laptop, so no camera direction is assumed;
                     distances are relative to the desk size
        |
   events            roles (cashier / client / collector / outsider / reflection in glass),
                     enter / exit, client sessions, cash on desk, counting, ID shown, door, safe
        |
   rules             one function per rule ID, thresholds from config/f1_codex.yaml
        |
   rank (max 3) --> attach norms (Knowledge Pack) --> cut evidence frames --> JSON
        |
GET /api/v1/jobs/{job_id}
```

Details, component list and what each rule relies on:
[`docs/ARCHITECTURE_SUMMARY.md`](docs/ARCHITECTURE_SUMMARY.md). Models and licences:
[`docs/MODELS.md`](docs/MODELS.md).

An alternative detector (`DETECTOR=vlm`, Qwen3.5-9B on vLLM filling a per-frame state form) is
kept in `backend/vlm/` with its tests, but it is not deployed: it was never measured on the full
dataset.

## Evaluation results

Measured on the **40 unique open videos** (42 files, two byte-identical duplicates) against the
organizer labels: 21 violation videos, 19 clean ones.

| Version | Correct verdicts /40 | Clean videos flagged /19 | Violations missed /21 |
| --- | --- | --- | --- |
| Always answer «violation» (floor) | 21 | 19 | 0 |
| A01, first CV checker | 20 | 13 | 7 |
| A17, deployed before the final round | 25 | 5 | 10 |
| **A20, deployed now** | **32** | **0** | **8** |

- **Recall 13/21, no false alarms on clean videos.** The offline replay and a run of all 42 files
  through the real API give the same verdicts; no job failed (wall time median 20 s, worst 89 s,
  with the perception cache warm; a cold run is slower, e.g. 50.8 s for one clip in A12).
- **Localization:** of the 13 caught violations, the finding is within ±1 / ±2 / ±3 / ±5 s of the
  organizer's second for 7 / 9 / 11 / 13; mean offset 1.54 s.
- **Robustness probes** (the same clips replayed as a nearer/farther camera, a mirrored camera, or
  a weaker detector): zoom 0.7-1.3 and mirror give exactly 32/0/8; dropping 20% of object
  detections gives 31-32 / 0 / 8-9.
- **Contract check** (`eval/check_outputs.py`, 24 dev clips): every response valid against the
  jury schema, none over 300 s.

**Conditions to keep in mind.** All 40 videos were used while building A20, so this is an
in-sample result: expect less on new videos. Robustness was checked only by geometric replay, not
on a real video from a new room or angle. The 8 misses are perception limits (states CLIP can't
read and small objects nobody detects) and are listed one by one in
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md). Every experiment, including the failed ones (A00-A22),
is in [`attempts/README.md`](attempts/README.md).

## Legal grounding

The law decides what counts as a possible violation, the models decide what happened in the
video, and a deterministic rule links the two. No LLM reads or searches the law while a video is
processed: all legal work is done beforehand, and the result is a fixed catalog of rules with
verbatim citations.

### Documents used

Only acts of the Republic of Kazakhstan (task.md FAQ 30), each taken from adilet.zan.kz in its
current редакция:

| Act | adilet.zan.kz | What it regulates | Used for | Редакция stored |
| --- | --- | --- | --- | --- |
| Постановление Правления НБРК **№ 231** от 29.11.2019 «Об утверждении Правил осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей…» (рег. МЮ № 19680) | [V1900019680](https://adilet.zan.kz/rus/docs/V1900019680) | Accepting, counting, paying out and storing cash; the cashier's workplace; cash collection | 12 of the 15 reported rules: leaving the desk, safe, mixing clients' cash, counting, ID, personal items, collection bags | 154 punkts (133 + 21 inserted by amendments); latest amendment in the footnotes: 30.06.2026 № 78 |
| Постановление Правления НБРК **№ 14** от 24.02.2020 «Об утверждении Правил организации охраны и устройства помещений банков…» (рег. МЮ № 20075) | [V2000020075](https://adilet.zan.kz/rus/docs/V2000020075) | Security and layout of the cash room: isolation, lockable door | Door left open, outsider in the cash room | 24 punkts; latest amendment: 24.12.2024 № 88 |
| Постановление Правления АРРФР **№ 53** от 03.04.2026 «Об утверждении Требований к обеспечению информационной безопасности банков…» | [V2600038336](https://adilet.zan.kz/rus/docs/V2600038336) | Information security, including workstation session locking | Laptop left unlocked (weak link, see below) | 162 punkts; no amendments |

Not cited: **НБРК № 48 от 27.03.2018** ([V1800016772](https://adilet.zan.kz/rus/docs/V1800016772)), the
earlier information security requirements. Act 53 repealed it (п. 2 of the постановление and its
list of repealed acts, item 1), so the build refuses any citation of it.

The full texts are in the repository, byte-for-byte as downloaded on 2026-10-18:
[`knowledge/sources/<act>/source.docx`](knowledge/sources/), with provenance in
[`knowledge/sources/sources.yaml`](knowledge/sources/sources.yaml) and a plain-text copy with the
punkt numbering restored (`text.txt`). adilet.zan.kz serves texts only through a JavaScript app
and a keyed API, so to refresh an act, download it again and replace its `source.docx`.

### How the documents are used

```
1. sources/*.docx --build_legal_catalog.py--> every punkt, part (ч.) and subpunkt (пп.) as a unit
2. each punkt reviewed: about the cash desk? visible on video? can the detector see it?
3. atomic requirements derived from the law alone, each matched to a rule, a gap or a rejection
4. knowledge/rulebook.yaml: act -> verbatim clause -> requirement -> visible breach -> rule
5. runtime: F1 rule fires -> Knowledge Pack attaches the clause, punkt, quote, link and status
```

- **Rulebook, the one source.** [`knowledge/rulebook.yaml`](knowledge/rulebook.yaml) holds every
  rule with its norms, verbatim quotes, what the video cannot show and the strength of each legal
  link: `direct` (the norm states the behaviour), `indirect` or `weak`. ADR:
  [`docs/adr/0001-rulebook-single-source.md`](docs/adr/0001-rulebook-single-source.md).
  `scripts/build_knowledge.py` generates the runtime Knowledge Pack (`knowledge/rules.yaml`,
  `knowledge/norms.json`), the F1 thresholds in `config/f1_codex.yaml`, and
  [`docs/RULES.md`](docs/RULES.md) and [`docs/VIOLATION_TYPES.md`](docs/VIOLATION_TYPES.md).
- **Catalog and source check.** `scripts/build_legal_catalog.py` splits the stored acts into
  units (`knowledge/legal_catalog.json`, 340 punkts) and finds every rulebook quote verbatim in
  the punkt, part or subpunkt it cites. All 20 quotes pass. `tests/test_legal_catalog.py` fails if
  a quote is not in the act, sits in another punkt, or cites the repealed act 48.
- **Independent review.** All 340 punkts were classified (`knowledge/legal_review.yaml`). Then
  77 atomic requirements were derived from the law without looking at the rulebook or the
  detector (`knowledge/legal_requirements.yaml`). Each was compared with the rules and with what
  `backend/f1/rules.py` actually reads (`knowledge/event_mapping.json`). The two-way matrix,
  law to rule and rule to law, is [`knowledge/coverage_matrix.md`](knowledge/coverage_matrix.md):
  8 requirements are implemented, 4 are implemented on a weak basis, 4 need new detection logic,
  48 cannot be established from video (amounts, signatures, packaging, rooms out of frame) and
  13 are not about the cash desk.
- **What it changed.** Links that overstated the law were lowered to `weak`:
  - the outsider and second-client rules (act 14 describes how the room is built, act 231 does not
    say «one client at a time»);
  - recount before the safe (231 п. 42 is about a controller's presence);
  - documents left on the desk (231 п. 80 refers to the bank's internal documents);
  - the screen lock (53 п. 71 пп. 9 sets a 30-minute auto-lock, not a duty to lock when leaving).

  A new rule from 231 п. 22, «кассир покинул рабочее место до окончания обслуживания клиента», is
  implemented but ships disabled. Replays gave it no finding on the open clips
  ([`attempts/A22-left-during-service-replay/`](attempts/A22-left-during-service-replay/)).
  Details: [`knowledge/README.md`](knowledge/README.md).

Each reported rule and its basis (first norm is the one shown in the description):

| Rule | Norms (strength) |
| --- | --- |
| `L-NO-CASH-ON-LEAVE` | 231 п. 20 ч. 2 (direct), п. 22 (direct) |
| `L-NO-DOCS-ON-LEAVE` | 231 п. 80 (weak) |
| `L-PC-LOCKED` | 53 п. 71 пп. 9) (weak) |
| `S-SAFE-CLOSED`, `S-CLEAN-DESK-HANDOVER` | 231 п. 20 ч. 2 (direct) |
| `S-NO-MERGE` | 231 п. 20 ч. 2 (direct), п. 21 (weak) |
| `A-OUTSIDER-ZONE` | 14 п. 16 пп. 1), п. 8 ч. 1 (weak) |
| `A-DOOR-LOCK` | 14 п. 16 пп. 1), п. 8 ч. 1 (indirect) |
| `A-SECOND-PERSON` | 231 п. 20 ч. 2, п. 21 (weak) |
| `C-COUNT-BEFORE-EXIT` | 231 п. 20 ч. 1 (direct) |
| `C-ID-BEFORE-CASH` | 231 п. 19 пп. 1) (direct), п. 7 (indirect) |
| `W-NO-PERSONAL-ITEMS` | 231 п. 12 ч. 1 (direct) |
| `W-NO-FOOD` | 231 п. 12 ч. 2 (weak) |
| `K-SEAL-CHECK` | 231 п. 24 пп. 3), 4) (direct) |
| `K-RECOUNT-BEFORE-SAFE` | 231 п. 74, п. 42 (weak) |

**Citation status.** A machine check proves that a quote is in the law. It does not prove that
the interpretation is right. A citation becomes `verified` only when a person has checked it on
adilet.zan.kz and recorded who and when; the service never marks one verified on its own. **As of
now all 20 norms are `pending`.** With `RULE_SCOPE=jury` the service reports only rules whose norms
are all verified and refuses to start while there are none, so the live service runs with
`RULE_SCOPE=detector`: every enabled rule is reported, and the UI marks its citation «ожидает
проверки».

## Tech stack

| Layer | Technology |
| --- | --- |
| Computer vision | PyTorch, Transformers, ONNX Runtime, OpenCV; RT-DETR r18vd, OWLv2, OpenCLIP ViT-B/32, RTMPose, ByteTrack (Supervision) |
| Backend | Python, FastAPI, Pydantic, uvicorn; SQLite job store; ffmpeg |
| Frontend | React, TypeScript (strict), Vite |
| Serving | Docker (multi-stage: Vite build + Python), Docker Compose, CUDA 12.8 wheels on one NVIDIA L4 |
| Alternative detector | vLLM serving Qwen3.5-9B FP8 (not deployed) |

All checkpoints are Apache-2.0 or MIT, pinned by revision and size in `models.lock.json`; the
download script refuses any other licence.

## Quick start

Requirements: Docker with Compose; an NVIDIA GPU with the container toolkit for the GPU profile
(the CPU profile works but is slower); Python 3.12+ to download the weights.

```bash
# 1. Weights: the only step that needs internet; sizes and hashes checked against models.lock.json
python3 scripts/download_weights.py            # -> ./weights

# 2. Settings
cp deploy/.env.example .env && chmod 600 .env
#   set API_KEY (e.g. `openssl rand -hex 32`)
#   set RULE_SCOPE=detector until the norms are human-verified (jury mode refuses to start)

# 3. Build and run (GPU)
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
#    or CPU only:  docker compose -f compose.yaml up -d --build

# 4. Check
curl -sf http://127.0.0.1:8000/healthz
curl -sf http://127.0.0.1:8000/readyz         # 200 once the weights match models.lock.json
```

The UI is then at http://127.0.0.1:8000/. The app binds to loopback by default; publishing it
(Brev proxy, Caddy, systemd) is covered in [`deploy/README.md`](deploy/README.md). All environment
variables and their defaults: `backend/config.py`.

Development:

```bash
.venv/bin/python -m pytest tests        # skips ffmpeg/GPU-only tests when unavailable
.venv/bin/ruff check backend
cd frontend && npm install && npm test && npx tsc --noEmit && npm run build
```

## API usage

Every `/api/v1` request needs the `X-API-Key` header; without a valid key the answer is `401`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/analyze` | Upload a video in the `file` field (`.mov`, `.mp4`, `.mkv`, up to 64 MiB). Returns `202` with `{"job_id": "..."}` |
| `GET` | `/api/v1/jobs/{job_id}` | Status and result: `processing`, `done` or `failed` |
| `GET` | `/api/v1/jobs/{job_id}/trace` | Debug trace of the detector (optional extra) |
| `GET` | `/healthz`, `/readyz` | Liveness and readiness, no key needed |

```bash
curl -X POST https://forte-checker-wwi4jcrss.gobrev.dev/api/v1/analyze \
     -H "X-API-Key: <key>" -F "file=@video_017.mov"
# -> {"job_id": "3f2a9c1e..."}

curl https://forte-checker-wwi4jcrss.gobrev.dev/api/v1/jobs/<job_id> \
     -H "X-API-Key: <key>"
```

A `done` result (illustrative and abridged; required jury fields first, the rest are optional
extras):

```json
{
  "job_id": "3f2a9c1e...",
  "status": "done",
  "verdict": "violation",
  "violations": [
    {
      "type": "Наличные/ценности оставлены без присмотра: кассир покинул рабочее место",
      "timecode_sec": 44.2,
      "description": "С 40.0 по 52.0 с кассир отсутствует на рабочем месте; на столе видны наличные. Признаки возможного нарушения: ... Основание: <название документа>, <пункт>.",
      "evidence_frames": [{ "timestamp_sec": 44.2, "image_base64": "/9j/4AAQ..." }],
      "rule_id": "L-NO-CASH-ON-LEAVE",
      "source": "Постановление НБРК №231, п.20, п.22",
      "source_quote": "...",
      "citation_status": "pending"
    }
  ],
  "warnings": [],
  "coverage": { "mode": "full", "step_s": 0.5, "deadline_hit": false }
}
```

Full contract and every field: [`docs/USAGE.md`](docs/USAGE.md) and `backend/contracts.py`.

## Project structure

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI service: API, job queue, pipeline, evidence, serialization. `backend/f1/` is the deployed detector (perception, calibration, events, rules); `backend/vlm/` the alternative one |
| `frontend/` | React + TypeScript UI, built into the service image |
| `knowledge/` | `rulebook.yaml` (rules and their legal basis), the Knowledge Pack generated from it, the stored acts (`sources/`) and the legal catalog, review and coverage matrix built from them |
| `config/` | Rule thresholds (`f1_codex.yaml`), perception prompts and thresholds (`perception.yaml`) |
| `scripts/` | Knowledge build (`build_knowledge.py`), legal catalog and source check (`build_legal_catalog.py`), weights download, F1 replay and robustness probes, jury client |
| `realtime/` | Live verdict gateway (separate container) |
| `eval/`, `validation/` | Scoring of API outputs against the private ground truth; pre-registered validation harness |
| `attempts/` | Every experiment A00-A22 with its result and logs |
| `tests/` | pytest suite; `tests/e2e/` acceptance suite against a deployed service |
| `deploy/` | Deployment runbook, Caddy, systemd, vLLM setup |
| `docs/` | Usage, architecture, models, rules, violation types, limitations, ADRs |
| `archive/` | History: research notes, superseded designs, raw VM workspace copies |

What is current and what is history: [`STATUS.md`](STATUS.md). Engineering rules for agents:
[`AGENTS.md`](AGENTS.md).

## Limitations

The full list with every known error case is [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md). The
main ones:

- **Recall first.** A missed violation is worse than a false alarm (task.md FAQ 16), so a finding
  is reported whenever an enabled rule's conditions hold, even with a pending citation.
- **Perception ceiling.** CLIP does not read whether the door, the safe door or the laptop screen
  is open, and keys, ID cards, seals and loose cash are often not detected. All 8 misses come from
  this, and two caught videos get the right verdict with the wrong violation type.
- **Not verified on new angles or rooms.** Only geometric replays were checked; the self-filmed
  robustness protocol ([`robustness/README.md`](robustness/README.md)) has no results yet.
- **In-sample numbers.** The 32/40 above was measured on the videos used to build the rules.
- **Legal basis pending.** No norm has been human-verified yet, so the service runs with
  `RULE_SCOPE=detector` and every citation is marked pending. Six reported rules rest only on
  `weak` links (see [Legal grounding](#legal-grounding)); their findings are visible facts, not
  established breaches of the cited punkt.
- **Short events.** At 2 fps with 0.6 s hysteresis, something visible for less than about a second
  can be missed.
- **One job at a time** on one L4 GPU. A second long video queued behind another can exceed the
  300 s limit.
- **At most 3 findings** per video; weaker ones on a busy video are not shown.
- **A hint, not a verdict.** Results are for human review, never a final disciplinary or legal
  conclusion. Only visual evidence is used: no audio, no face recognition, no data that is not
  in the frame.

## Privacy

Dataset videos/frames, runtime uploads, model weights and credentials are excluded by
default. Checked-in attempts contain public-development labels, numeric predictions and
textual observations for reproducibility; see `CONTEXT.md`. No cloud AI processes dataset
media. API uploads and evidence retention are described in `docs/LIMITATIONS.md`.
