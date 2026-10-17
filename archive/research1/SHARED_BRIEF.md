# Shared brief for all work-package agents (read fully before coding)

Repo: /home/yertugan/Repositories/hackathon. Python venv: `.venv/bin/python` (3.12; fastapi, pydantic v2,
httpx, PyYAML, pillow, pytest, ruff, numpy, openpyxl, uvicorn, python-multipart are installed).
Do NOT install torch/transformers/opencv/vLLM locally. Do NOT pip install anything else without saying
so in your final report (and prefer not to). There is no GPU, no ffmpeg/ffprobe on this machine:
tests that need ffmpeg must use `pytest.mark.skipif(shutil.which("ffmpeg") is None, reason=...)`.

Read first: `AGENTS.md`, `backend/AGENTS.md` (or `frontend/AGENTS.md`), `archive/research1/implementation-plan.md`
(your WP section), `archive/research1/architecture.md`, and `backend/contracts.py`.

## Hard rules
1. **File ownership.** Only create/edit files in your WP's file set (listed in your prompt). Four agents
   work in this same tree at the same time. If you need a change in someone else's file, do not make
   it: write it under "Requests to other WPs" in your final report.
2. **`backend/contracts.py` is frozen.** Import from it; never redefine its types; never edit it.
   If it truly blocks you, report the needed change instead.
3. **Privacy / competition rule (disqualification risk).** Organizer videos, frames, labels and
   VLM state outputs are private. Never open, print, cat, or view: anything under `data/open/`,
   `*.mov`, extracted frames/JPEGs, `open_labels.xlsx`, `results.json`, any `states/` or
   `violations/` per-video JSON, or `.env` files. You may read code, schemas (`questionnaire_v1.json`,
   `FEATURES.md`), prompts, YAML/JSON *config* and docs. If you must learn a data file's shape, print
   only key names and types via a short script, never values. Scripts you run over private data may
   print aggregate numbers only. Never send any of it anywhere over the network.
4. **No git commits, no pushes, no ssh to any VM.** Work locally only.
5. **No invented results.** No mocks or fake fallbacks in production code. Test doubles are fine
   inside `tests/`. Errors are explicit; never a fabricated `no_violation`.
6. Legal citations: an AI never marks a norm `human_verified: true`. Humans verify on adilet.zan.kz.
7. Python: ruff-clean (`.venv/bin/ruff check <your files>` and `ruff format`), type hints, thin
   handlers, pure domain functions. Run your tests with `.venv/bin/python -m pytest <your tests>`.
   Never claim a test passed unless it ran.

## Source material (read-only, gitignored snapshot of the VM workspaces)
- Base app (already imported into the repo by the orchestrator): `archive/vm-copies/datathon/forte-model-check-20261017-1114/`
- VLM kit: `archive/vm-copies/datathon/forte_brev_kit/brev_kit/` — `scripts/run_vlm.py`, `scripts/timeline_rules.py`,
  `scripts/common.py`, `schema/questionnaire_v1.json`, `prompts/`, `prompts_v2/`, `FEATURES.md`,
  `codex/codex_verified.json`, `tests/make_fixture_states.py`, `tests/mock_vlm_server.py`, `serve_datathon.sh`.
- R1 scorer: `validation/validation-evidence/harness/score.py`, `score_utils.py`, `gt.py`, `split.py`.

## What the orchestrator already did (kickoff)
- Shell modules copied to `backend/`: `main.py config.py store.py worker.py pipeline.py evidence.py models.py`
  (imports still point at old paths; WP1 fixes them).
- F1 stack copied to `backend/f1/`: `perception.py events.py rules.py calibration.py vision_types.py codex.py`
  (imports still say `backend.rules`, `backend.codex`, ...; WP1 fixes them). F1 codex: `config/f1_codex.yaml`.
- Old tests: `tests/test_f1_rules.py`, `tests/test_api_smoke.py` (WP1 owns both).
- Frontend copied into `frontend/`. Old docs into `docs/` (`LIMITATIONS.md`, `MODELS.md`, `F1_RULES.md`).
- `archive/vm-copies/` added to `.gitignore`.

## Agreed interfaces (beyond contracts.py) — implement exactly these names/signatures

WP1 (platform):
- `backend/media.py`:
  - `probe(video: Path) -> VideoInfo` (ffprobe; raises `MediaError(ValueError)` on unreadable / >180 s / no video stream)
  - `extract_jpeg(video: Path, t: float, max_side: int | None = None, quality: int = 90) -> bytes`
    (ffmpeg seek, JPEG bytes; raises `MediaError`). WP2's sampler and WP1's evidence both use this one function.
- `backend/plan.py`: `build_plan(info: VideoInfo, deadline_monotonic: float, coarse_step_s: float = 4.0, fill_step_s: float = 2.0) -> SamplingPlan`
  (coarse = 0,4,8,... plus the last second; fill = midpoints between consecutive coarse times, not duplicating any coarse time).
- `backend/f1/detector.py`: `class F1Detector` implementing `Detector`.
- `backend/config.py`: `Settings` (env-driven) with `detector: Literal["vlm","f1"]`, `knowledge_dir`, `job_budget_s = 270`,
  and `vlm: VlmSettings` built from `VLM_*` env vars.
- `backend/pipeline.py`: orchestrates probe → build_plan → detector.detect → `rules.rank` → `Knowledge.ground` → evidence → `serialize.to_done_job`.

WP2 (VLM):
- `backend/vlm/config.py`: `class VlmSettings(BaseModel)`: `base_url: str = "http://127.0.0.1:8010/v1"`, `model: str`,
  `max_side: int = 768`, `max_in_flight: int = 8`, `request_timeout_s: float = 60.0`, `stop_margin_s: float = 15.0`,
  `max_failed_frac: float = 0.30`, `fill_step_s: float = 2.0` (+ any more fields WP2 needs, all with defaults except `model`).
- `backend/vlm/detector.py`: `class VlmDetector` with `__init__(self, settings: VlmSettings, rules: list[RuleEntry])` and
  `detect(self, video: Path, info: VideoInfo, plan: SamplingPlan) -> DetectionResult`. It builds a `StateTimeline`
  and calls WP3's `backend.rules.evaluate(timeline, rules)`. Raises `VlmUnavailableError` (vLLM unreachable) and
  `TooManyFailedFramesError` (failed > max_failed_frac); both subclass `backend.vlm.errors.VlmError(RuntimeError)`.
- `backend/vlm/client.py`: `check_ready(settings) -> bool` (GET `{base_url}/models`), used by WP1's `/readyz`.

WP3 (rules + knowledge):
- `backend/rules/__init__.py` re-exports `evaluate` and `rank`.
  - `evaluate(timeline: StateTimeline, rules: list[RuleEntry]) -> list[Finding]` — pure; only `enabled` rules; params from `RuleEntry.params`.
  - `rank(findings: list[Finding], rules: list[RuleEntry], cap: int = 3) -> list[Finding]` — persistence first, then rule order.
- `backend/knowledge.py`: `class KnowledgeError(ValueError)`, `class Knowledge` with
  - `@classmethod load(cls, root: Path) -> Knowledge` (reads `root/rules.yaml` and `root/norms.json`; raises `KnowledgeError` on unknown norm id, enabled rule without norms, duplicate ids, schema errors)
  - `rules: list[RuleEntry]`, `enabled_rules() -> list[RuleEntry]`, `rule(rule_id: str) -> RuleEntry` (raises `KnowledgeError`)
  - `ground(findings: list[Finding]) -> list[GroundedFinding]` (`citation_status` = `verified` only if every norm is `human_verified`)
  - `describe(g: GroundedFinding) -> str` — the jury `description`: observation (template filled from `facts` + `{t}`) and the
    claim "признаки возможного нарушения: <title_ru>". The one place templates are filled.
- Knowledge Pack files: `knowledge/rules.yaml`, `knowledge/norms.json`; canonical rule IDs per architecture.md §3
  (e.g. `L-NO-CASH-ON-LEAVE`). F1Detector must emit these same IDs.

WP1 serializer mapping (`backend/serialize.py`): `Violation.type = rule.title_ru`, `description = knowledge.describe(g)`,
`timecode_sec = finding.t_anchor`, `rule_id`, `source = "<act>, <punkt>"` of the primary norm, `source_url`,
`source_quote` (primary norm's verbatim quote; added to contracts.py at kickoff for the UI norm block), `strength`,
`citation_status`. `verdict = "violation"` iff violations non-empty. `coverage` and `warnings` copied from `DetectionResult`.

WP4 (frontend/docs) consumes the `DoneJob` JSON shape above (including the optional extras and `coverage`).

## Final report (keep it under ~60 lines)
Files created/changed; interface deviations (should be none); commands you ran and their real results
(test counts, ruff, tsc); what is stubbed/untested and why; "Requests to other WPs"; open human tasks.
