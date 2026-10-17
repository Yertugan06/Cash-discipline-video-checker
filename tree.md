# Project structure

> Lines are at most 80 characters wide. What is current vs history, and the
> paths that moved on 2026-10-17: `STATUS.md`.

## Root

```text
datathon26/
├── README.md            - overview, submission table, dev setup
├── STATUS.md            - current vs archive, label sources, path map
├── CONTEXT.md           - working notes for agents (machines, results)
├── OPEN_ISSUES.md       - known problems not fixed yet
├── AGENTS.md            - engineering rules for agents
├── task.md              - competition brief and evaluation rules
├── Dockerfile           - app image: frontend build + Python backend
├── compose.yaml         - base compose service (host network, :8000)
├── compose.gpu.yaml     - overlay: CUDA build + GPU for DETECTOR=f1
├── compose.cloud.yaml   - dev overlay: mounts source over the image
├── models.lock.json     - pinned model revisions, files, sha256, licences
├── pyproject.toml       - project metadata, pytest and ruff settings
├── requirements*.txt    - runtime and dev Python dependencies
├── backend/             - FastAPI service (current)
├── frontend/            - React + TypeScript UI (current)
├── realtime/            - live verdict gateway, WebSocket (current)
├── config/              - detector config and rule thresholds (current)
├── knowledge/           - Knowledge Pack: rules and norms (current)
├── scripts/             - build, download and replay tools (current)
├── deploy/              - deployment runbook and units (current)
├── docs/                - submission docs, task.md §8 (current)
├── tests/               - pytest suite and e2e acceptance suite
├── data/                - team workbooks, gateway label index
├── eval/                - scores API outputs with the validation scorer
├── validation/          - validation harness, scorer, private gt
├── attempts/            - every experiment: result, logs (A00-A13)
├── robustness/          - other-angle filming protocol
└── archive/             - history: research, VM copies, old docs
```

## backend/

Pipeline: probe -> plan -> detect (F1) -> rank -> ground -> evidence ->
serialize.

```text
backend/
├── AGENTS.md        - backend ownership and coding rules
├── main.py          - FastAPI app, routes, auth, detector selection
├── config.py        - Settings from env (DETECTOR=f1 by default)
├── contracts.py     - Pydantic models: Finding, DoneJob, Coverage, ...
├── pipeline.py      - orchestration of one job
├── worker.py        - one-job-at-a-time FIFO worker, result purge
├── store.py         - SQLite job store with TTL purge
├── media.py         - ffprobe validation, frame extraction
├── plan.py          - deadline-aware plan (4 s grid + 2 s fill; VLM)
├── evidence.py      - 1-3 JPEGs from the source video, trigger boxes
├── knowledge.py     - rule_id -> norms lookup, citation_status
├── serialize.py     - internal result -> jury JSON contract
├── f1/              - deployed detector (CV stack)
│   ├── detector.py      - F1Detector: frames, perception, rules, trace
│   ├── perception.py    - RT-DETR, OWLv2, OpenCLIP, RTMPose, cache
│   ├── calibration.py   - scene objects, cashier/client zones
│   ├── events.py        - observations -> event timeline
│   ├── rules.py         - one function per rule id
│   ├── codex.py         - loads config/f1_codex.yaml
│   └── vision_types.py  - Box, Detection, Observation, Scene, State
├── rules/
│   ├── ranking.py       - rank findings and cap at 3
│   └── timeline.py      - state-timeline rules (VLM detector)
└── vlm/             - alternative detector, not deployed
    ├── detector.py      - VlmDetector
    ├── client.py        - vLLM client
    ├── sampler.py       - coarse-then-fill frame sampling
    ├── config.py, errors.py
    ├── form_schema.json - per-frame state form schema
    └── prompts/         - system.txt, questionnaire.txt
```

## frontend/

```text
frontend/
├── AGENTS.md, index.html, package.json, tsconfig.json, vite.config.ts
└── src/
    ├── App.tsx          - upload, polling, verdict view
    ├── api.ts           - HTTP client for the backend API
    ├── contract.ts      - TypeScript types for the jury contract
    ├── messages.ts      - UI strings and violation texts
    ├── main.tsx, style.css
    ├── components/      - CoverageWarning, NormBlock, ViolationCard
    ├── fixtures/        - sampleDoneJob.ts
    └── *.test.mjs       - api, fixtures, messages, privacy tests
```

## realtime/

```text
realtime/
├── gateway.py       - folder queue -> API jobs -> WebSocket verdicts
├── static/index.html - live verdict page
├── Dockerfile, requirements.txt, README.md
```

## config/, knowledge/, data/

```text
config/
├── f1_codex.yaml        - rules and thresholds (from the rulebook xlsx)
├── perception.yaml      - prompts, score thresholds, intervals
├── overrides.yaml       - manual zones per video SHA-256 (empty)
└── rule_templates.yaml  - input for scripts/convert_codex.py

knowledge/
├── rules.yaml           - canonical rules, RU/EN titles, templates
├── norms.json           - norm texts and adilet links
└── README.md            - provenance and open conflicts

data/                    - see data/README.md
├── Cash_Discipline_Cases_Rules.xlsx - rulebook -> config/f1_codex.yaml
├── Таблица_нарушений.xlsx           - annotation -> gt.json human
└── prepared/videos.jsonl            - label index for realtime/
```

## scripts/

```text
scripts/
├── convert_codex.py     - rulebook xlsx -> config/f1_codex.yaml
├── build_knowledge.py   - codex sources -> knowledge/
├── render_rules_doc.py  - knowledge/ -> docs/RULES.md
├── download_weights.py  - fetch pinned weights (+ .sh wrapper)
├── check_models.py      - run model adapters on synthetic pixels
├── jury_client.py       - submit a video like the jury does
├── replay_f1.py         - replay cached F1 perception, score runs
├── bench_vlm.py         - VLM throughput benchmark (alternative path)
└── gen_form_schema.py   - regenerate backend/vlm/form_schema.json
```

## docs/, deploy/, tests/, eval/

```text
docs/
├── USAGE.md             - API, UI, running it, key handover
├── ARCHITECTURE_SUMMARY.md - F1 flow, components, locality
├── MODELS.md            - models and licences
├── VIOLATION_TYPES.md   - violation families the service checks
├── RULES.md             - rule -> norm mapping (generated)
└── LIMITATIONS.md       - known limitations and failure modes

deploy/
├── README.md, .env.example
├── Caddyfile            - reverse proxy (not installed on datathon)
├── forte-checker.service - systemd unit for the app
└── vllm/                - vLLM serving for the alternative detector

tests/                   - test_*.py per module, e2e/, fixtures/
eval/
├── run_eval.py          - DoneJob JSONs -> validation scorer
└── kit_states_adapter.py - load the kit's saved VLM states
```

## validation/, attempts/, archive/

```text
validation/
├── validation-evidence/
│   ├── PREREGISTRATION.md   - frozen protocol, dev/lockbox split
│   ├── harness/             - score.py, gt.py, split.py (current) and
│   │                          experiment scripts behind A00, A04-A09
│   ├── verify/, data-audit/ - scorer and data checks
│   └── logs/                - experiment logs
└── validation-private/      - gt.json, split.json, preds/, detections

attempts/
├── README.md            - map of every attempt and its result
├── _template/           - copy for a new attempt
└── A00-... A13-...      - one folder per attempt: README, logs, scripts

archive/                 - see archive/README.md
├── research1/           - research notes, ADR-001, ADR-002
├── docs-vlm-era/        - docs from the VLM-first design
├── vm-copies/           - raw VM workspaces (kits, teammate apps)
├── agents/, skills/     - research-phase agent prompts and skills
└── data-prepared-old/   - old structured copy of the workbook
```
