# Project Structure: Forte Cash-Discipline Video Checker

> Compact layout designed for non-wrapping viewers (`wrap=false`).
> Every line is strictly ≤ 80 characters wide to fit split screens.

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Backend Service (`backend/`)](#2-backend-service)
3. [Frontend Application (`frontend/`)](#3-frontend-application)
4. [Knowledge, Configs & Data](#4-knowledge-configs--data)
5. [Test Suite & Validation](#5-test-suite--validation)
6. [Deployment & Automation](#6-deployment--automation)
7. [Research & Experiments](#7-research--experiments)
8. [Agent Personas & Skills (`agents/`, `skills/`)](#8-agents--skills)

---

## 1. High-Level Architecture

```text
datathon26/
├── AGENTS.md            — Multi-agent engineering principles & guidelines
├── CONTEXT.md           — Global architecture rules & constraints
├── Dockerfile           — Multi-stage build for backend & frontend
├── README.md            — Overview, submission links & dev setup
├── compose.cloud.yaml   — Compose for remote cloud GPU deployment
├── compose.gpu.yaml     — Compose with NVIDIA GPU pass-through
├── compose.yaml         — Base local Docker Compose specification
├── models.lock.json     — Model checksums & open licenses
├── pyproject.toml       — Project metadata, deps & linter rules
├── requirements.txt     — Production deps (FastAPI, PyTorch, CV)
├── requirements-dev.txt — Development dependencies (pytest, ruff)
├── task.md              — Competition specs & evaluation rules
├── .dockerignore        — Docker build context exclusion list
├── .gitignore           — Untracked files (caches, videos, DBs)
├── agents/              — Prompts for autonomous review agents
├── attempts/            — Experiment logs & ablation sweeps (A00–A12)
├── backend/             — FastAPI service: CV perception, rules & VLM
├── config/              — YAML configs for perception & rule codex
├── data/                — Domain rule spreadsheets & video datasets
├── deploy/              — Production runbooks, Caddyfile & services
├── docs/                — Architecture, models, rules & user guides
├── eval/                — Benchmark scoring runner & metric calculators
├── frontend/            — React + TypeScript web interface
├── knowledge/           — Compliance rule definitions & bank norms
├── realtime/            — WebSocket gateway for live stream audit
├── archive/research1/          — Authoritative ADRs, harness & metrics
├── archive/vm-copies/          — [Ignored] Archive of exploratory team repos
├── robustness/          — Evaluation across camera angles & lighting
├── scripts/             — Automation CLI tools (downloader, jury)
├── skills/              — Methodologies for problem investigation
└── tests/               — Pytest test suite (unit, e2e, security)
```

---

## 2. Backend Service

Pipeline: Stage 1 (CV/YOLO) → Stage 2 (VLM) → Stage 3 (Rules) → Evidence.

```text
backend/
├── AGENTS.md        — Backend coding guidelines & ownership rules
├── config.py        — Central environment & configuration loader
├── contracts.py     — Pydantic schemas for API & domain models
├── evidence.py      — Extracts & crops 1–3 best evidence frames
├── knowledge.py     — Grounding service linking violations to norms
├── main.py          — FastAPI app entrypoint, CORS & REST routes
├── media.py         — Video decoding & OpenCV frame extraction
├── pipeline.py      — Main orchestrator coordinating CV, VLM & rules
├── plan.py          — Planner allocating sampling rates per clip
├── serialize.py     — Serializes outputs into strict JSON schema
├── store.py         — Thread-safe job state tracker for background runs
├── worker.py        — Asynchronous background worker processing jobs
│
├── f1/              — Stage 1: Fast CV Perception & Detector
│   ├── calibration.py   — Camera classification & zone calibration
│   ├── codex.py         — Translates visual events into codex codes
│   ├── detector.py      — YOLO detector tracking people, phones & bags
│   ├── events.py        — Detects domain events (phones, cash left)
│   ├── perception.py    — Low-level frame perception & motion tracking
│   ├── rules.py         — Heuristic rule evaluation on event streams
│   └── vision_types.py  — Dataclasses for boxes, tracks & events
│
├── rules/           — Violation Aggregation & Prioritization
│   ├── ranking.py       — Deduplication, severity sort & confidence
│   └── timeline.py      — Temporal clustering into continuous intervals
│
└── vlm/             — Stage 2: Vision-Language Model Verification
    ├── client.py        — Async HTTP client calling local vLLM endpoint
    ├── config.py        — VLM endpoint URLs, model name & generation
    ├── detector.py      — Formulates visual queries & parses verdicts
    ├── errors.py        — Custom exception definitions for VLM
    ├── form_schema.json — JSON schema enforcing structured VLM answers
    ├── sampler.py       — Selects high-motion & keyframes for VLM
    └── prompts/
        ├── questionnaire.txt — Multi-question visual inspection prompt
        └── system.txt        — System prompt defining auditor persona
```

---

## 3. Frontend Application

React 18 + TypeScript SPA for video upload, verdicts, and evidence review.

```text
frontend/
├── AGENTS.md        — Frontend development guidelines & state rules
├── index.html       — HTML shell with root mounting point
├── package.json     — Dependencies (React, Lucide icons, Vite)
├── tsconfig.json    — Strict TypeScript compiler configuration
├── vite.config.ts   — Vite dev server & build pipeline setup
│
└── src/
    ├── App.tsx          — Root component: upload, polling & verdict
    ├── api.ts           — Type-safe HTTP client for backend REST API
    ├── contract.ts      — TypeScript interfaces matching backend models
    ├── main.tsx         — React application bootstrap entrypoint
    ├── messages.ts      — UI localization strings & violation texts
    ├── style.css        — Clean, responsive layout styling
    │
    ├── components/
    │   ├── CoverageWarning.tsx — Quality limitation warning banner
    │   ├── NormBlock.tsx       — Component rendering legal citations
    │   └── ViolationCard.tsx   — Displays violation, time & evidence
    │
    ├── fixtures/
    │   └── sampleDoneJob.ts    — Mock completed job for UI tests
    │
    └── tests/
        ├── api.test.mjs        — Unit tests for API client errors
        ├── fixtures.test.mjs   — Contract tests for fixture schemas
        ├── messages.test.mjs   — Localization completeness checks
        └── privacy.test.mjs    — Verifies zero external network calls
```

---

## 4. Knowledge, Configs & Data

Regulatory rules, legal citations, perception settings, and datasets.

```text
knowledge/
├── README.md            — Documentation on compliance knowledge grounding
├── norms.json           — Regulatory articles mapped to violation codes
└── rules.yaml           — Canonical codex: conditions, severities & titles

config/
├── f1_codex.yaml        — Rule mapping configuration for Stage 1 CV
├── overrides.yaml       — Sensitivity & confidence threshold overrides
├── perception.yaml      — YOLO model weights, target classes & ROIs
└── rule_templates.yaml  — Text templates for violation descriptions

data/
├── Cash_Discipline_Cases_Rules.xlsx — Domain cashier discipline rules
├── Таблица_нарушений.xlsx           — Official competition rule table
└── prepared/
    ├── README.md                — Documentation for benchmark manifests
    ├── events.jsonl             — Ground-truth events with timecodes
    ├── schema.json              — JSON schema validating dataset entries
    ├── validation_report.json   — Dataset audit report & health metrics
    └── videos.jsonl             — Catalog of benchmark clips & metadata
```

---

## 5. Test Suite & Validation

Verification of API contracts, pipeline logic, and metric scoring.

```text
tests/
├── conftest.py              — Pytest fixtures, mock generators & server
├── test_api.py              — REST API route and validation tests
├── test_eval_run_eval.py    — Offline metric calculation verification
├── test_evidence.py         — Tests evidence extraction & cropping
├── test_f1_detector.py      — YOLO detector bounding box tests
├── test_f1_rules.py         — Heuristic rule evaluation tests
├── test_knowledge.py        — Validates rules.yaml & norm mappings
├── test_media.py            — Video loading, decoding & FPS tests
├── test_no_label_access.py  — Security check: zero access to labels
├── test_pipeline.py         — End-to-end integration test of pipeline
├── test_plan.py             — Pipeline execution planner tests
├── test_realtime_gateway.py — Tests WebSocket live streaming gateway
├── test_rules_equivalence.py— Ensures refactored rules stay consistent
├── test_rules_ranking.py    — Tests violation ranking & deduplication
├── test_rules_timeline.py   — Tests temporal interval merging logic
├── test_serialize.py        — Tests JSON serialization compliance
├── test_vlm_client.py       — Tests VLM HTTP client & retries
├── test_vlm_detector.py     — Tests VLM structured answer parsing
├── test_vlm_sampler.py      — Tests keyframe selection algorithms
├── test_vlm_schema.py       — Validates adherence to VLM JSON schema
│
├── e2e/
│   └── test_e2e.py          — Full system acceptance tests on sample clips
└── fixtures/
    ├── rules/builder.py     — Mock rule builders for unit tests
    └── vlm/frame.jpg        — Mock cashier frame for VLM testing

eval/
├── README.md                — Guide for running benchmark evaluation
├── kit_states_adapter.py    — Adapter translating internal states
└── run_eval.py              — Benchmark scoring runner (P, R, F1)

robustness/
└── README.md                — Protocol across varied angles & lighting
```

---

## 6. Deployment & Automation

Production runbooks, systemd services, Caddy reverse proxy, and CLI tools.

```text
deploy/
├── .env.example             — Example environment variables
├── Caddyfile                — Caddy HTTPS reverse proxy config
├── README.md                — Deployment runbook for GPU servers
├── forte-checker.service    — Systemd unit for backend FastAPI
└── vllm/
    ├── requirements-vllm.txt— Python dependencies for vLLM server
    ├── serve.sh             — Server startup script with GPU tuning
    └── vllm.service         — Systemd unit for background vLLM daemon

scripts/
├── bench_vlm.py             — Measures VLM latency & throughput
├── build_knowledge.py       — Compiles Excel sheets into YAML/JSON
├── check_models.py          — Confirms local model weights & hashes
├── convert_codex.py         — Converts legacy codex into YAML structure
├── download_weights.py      — Downloads approved weights from HF
├── download_weights.sh      — Shell wrapper for model downloads
├── gen_form_schema.py       — Generates JSON schema for questionnaires
├── jury_client.py           — Automated client simulating jury curls
└── render_rules_doc.py      — Generates docs/RULES.md markdown table

realtime/
├── README.md                — Real-time streaming documentation
├── gateway.py               — WebSocket server for live stream analysis
└── static/index.html        — Interactive browser UI for live testing
```

---

## 7. Research & Experiments

Ablations, architectural decisions, and experiment progression.

```text
attempts/
├── README.md                    — Chronological index of all attempts
├── _template/README.md          — Standardized template for experiments
├── A00-baselines/               — Heuristic & random score baselines
├── A01-f1-cv-checker-v1/        — Stage 1 CV detector ablation logs
├── A02-vlm-qwen35-9b-questionnaire/ — Questionnaire VLM evaluation
├── A03-vlm-qwen35-9b-prompts-v2/— Refined VLM prompts with zoomed crops
├── A04-f3-whole-video-vlm/      — Full-video VLM feasibility study
├── A05-f4-cascade/              — Two-stage cascade: motion + VLM
├── A06-f1-zone-free-coco/       — General COCO detection without zones
├── A07-f2-embedding-probe/      — Feature embedding anomaly probing
├── A08-vlm-window-verifier/     — Sliding-window temporal verification
├── A09-kit-rule-sweep/          — Global threshold sweep across codex
├── A10-agentA-rulebook/         — Rulebook pipeline by Agent A
├── A11-agentB-hybrid/           — Hybrid CV+VLM pipeline by Agent B
└── A12-adr002-service-f1/       — Production candidate validation & traces

archive/research1/
├── SHARED_BRIEF.md              — Shared problem brief & constraints
├── architecture-decision.md     — ADR-002: Two-stage cascade decision
├── architecture.md              — Authoritative architecture specification
├── data-exploration.md          — Video properties & camera perspectives
├── implementation-plan.md       — Engineering milestones & work breakdown
├── problem-exploration.md       — Domain analysis of cash discipline
├── problem-reframing.md         — Reframing task as visual verification
├── problem-validation.md        — Pre-registered benchmark metrics & gates
├── senior-ideas.md              — Architectural proposals & trade-offs
├── solution-decision.md         — Formal solution selection rationale
├── technology-research-landscape.md — Comparative study of CV & VLMs
├── validation-evidence/
│   ├── PREREGISTRATION.md       — Pre-registered hypotheses before tests
│   ├── data-audit/              — Scripts checking label distributions
│   ├── harness/                 — Benchmark evaluation runners & scoring
│   └── logs/                    — Benchmark run outputs & score records
└── validation-private/          — [Ignored] Cached features & split labels

archive/vm-copies/                      — [Ignored in git] VM workspace copy
└── datathon/                    — Archived exploratory repos & spikes
```

---

## 8. Agents & Skills

System prompts and structured methodology workflows.

```text
agents/
├── adversarial-evaluator.md — Challenges assumptions & edge-case flaws
├── independent-verifier.md  — Validates implementation against task specs
├── solution-critic.md       — Conducts architectural reviews & flags risks
└── solution-investigator.md — Investigates detector discrepancies

skills/
├── idea_generation.md       — Framework for brainstorming CV heuristics
├── problem-explore/         — Methodology for exploratory video audit
├── problem-reframe/         — Converting qualitative rules to CV signals
└── problem-validate/        — Guide for controlled hypothesis experiments
```
