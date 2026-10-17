# Archive

History of the project: kept for reference and for reproducing past
experiments, not used by the running service. Results and their write-ups
are indexed in `attempts/README.md`; this page says which raw material backs
which attempt. Current vs archived paths are listed in `STATUS.md`.

| Folder | Contents | Backs |
|---|---|---|
| `research1/` | Research notes from 2026-10-17: `problem-exploration.md`, `problem-reframing.md`, `data-exploration.md`, `technology-research-landscape.md`, `senior-ideas.md`, `problem-validation.md` (results of the pre-registered validation), `solution-decision.md` (ADR-001, superseded), `architecture-decision.md` (ADR-002), `architecture.md`, `implementation-plan.md`, `SHARED_BRIEF.md` (brief for the work-package agents) | A00, A04-A09 write-up (`problem-validation.md`); the service design |
| `docs-vlm-era/` | Docs written while the VLM was the planned main detector | design history |
| `vm-copies/datathon/forte-model-check-20261017-1114/` (`forte-cash-checker` is a symlink to it) | Teammate F1 CV checker, the code the service's `backend/f1/` was ported from | A01 |
| `vm-copies/datathon/forte_brev_kit/` | VLM questionnaire kit (Qwen3.5-9B on vLLM), its runs, gold frames, contact sheets, `codex/codex_verified.json` | A02, A03; A09 re-scores A02's saved states |
| `vm-copies/datathon/dt26-validation/` | Copy of the validation harness as it was on the VM. The canonical harness and the logs for A04-A08 are in `validation/` | (copy) |
| `vm-copies/datathon/from-datathon2/agentA-rulebook/` | Rulebook variant of the F1 checker, from the stopped `datathon2` VM | A10 |
| `vm-copies/datathon/agentB-hybrid/` | Hybrid F1 + VLM probe experiment | A11 |
| `vm-copies/datathon/spike_out/`, `spike_out_vlm/` | Detection spike outputs and HTML reports | A13 |
| `agents/`, `skills/` | Agent prompts and research skills used during problem exploration | process |
| `data-prepared-old/` | Structured copy of the team workbook (`events.jsonl`, `schema.json`, `validation_report.json`), files dated 17:55, built by a `prepare_data.py` that is no longer in the repo | process |

Don't edit files here to change behaviour. If something in the archive is
needed again, move it back out and update `STATUS.md`.
