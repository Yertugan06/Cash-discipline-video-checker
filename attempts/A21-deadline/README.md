# A21 — deadline perception and evidence repair

Started 2026-10-18 02:41 UTC; user authorized implementation with four remote workers and
3.5 hours remaining. Target finish before 06:05 UTC, with integration/checkpoints well before it.

Status: final one-VM API run complete: **30/40 unique verdicts, 0/19 clean false alarms,
42/42 jobs successful** with local Qwen3-VL-4B safe-state checks enabled at the user's request. The implementation builds on main `2c5db9a`; reviewed source, tests and evidence are published together. See [results and release details](RESULTS.md) for accepted changes,
rejected model experiments, measurements, source locations and remaining gaps. A20's 32/40
included two findings contradicted by the supplied human observations.

| Worker | Task ID | Ownership / purpose |
|---|---|---|
| datathon2 / 1 | a21-recognition-0246 | Small-object crop comparison; perception/refinement only |
| datathon2 / 2 | a21-visual-checks-0246 | Bounded local VLM state verification and detector integration |
| datathon3 / 1 | a21-evidence-0246 | Honest event/rule evidence and uncertainty guards |
| datathon3 / 2 | a21-validation-0246 | Independent verdict/reason/timing audit |

All four accepted submission through `codex-worker submit`; base `7bc47e7`, clean worktrees.
The orchestrator reviews patches/results and runs GPU commands outside worker sandboxes.
One GPU-heavy job per VM, protected by `~/.cache/datathon-workers/gpu.lock`.

The actual first-turn session records on both VMs confirm **gpt-6.1-sol / max** for all four
workers. The user subsequently requested Ponytail. Its exact SKILL.md was installed on both VMs;
the launcher now prepends an explicit `$ponytail` instruction to subsequent submissions. Existing
one-shot exec jobs have no live steering socket; apply the skill explicitly at their next review
turn/checkpoint, preserving their in-flight work. Do not claim they received a live user message.

Shared interfaces, constraints and human clarifications: [common brief](briefs/common.md).
Tasks: [recognition](briefs/d2-1-recognition.md), [visual checks](briefs/d2-2-visual-checks.md),
[evidence](briefs/d3-1-evidence.md), [validation](briefs/d3-2-validation.md).

No dataset frame/video is sent to cloud AI or an image-viewing tool. All visual inference runs
locally on the authorized VMs. Only code, numeric traces and text results return for review.
Existing services/annotations and unrelated dirty work stay intact. Pre-implementation backup:
`/tmp/a21-before-implementation-20261018T024306Z/` (48 working files plus binary tracked diff).

## Acceptance

Separate object recognition, association, observable events, policy applicability and organizer
verdict agreement. Preserve recording cutoffs/unknown states. No filename, appearance, desk-side
or fixed-time exceptions; no wrong-rule catch preserved merely for the score. Retain paired and
duplicate grouping, and expose sparse human reason coverage. Report real runtime and unrun checks.

The first checkpoint is a useful CPU implementation/validation artifact in 25–40 minutes and
a runnable local model probe. Then integrate only reviewed generic improvements, perform a real
local inference comparison and a full unique-clip replay/API validation on the chosen candidate.
Cold runtime and unsupported explanations are acceptance concerns alongside missed/clean clips.

## Work log

- 02:41 UTC: implementation authorized; both VMs and all worktrees checked. datathon2 L4 had
  2.2 GiB resident allocation, datathon3 L4 idle; no existing process was stopped.
- 02:43 UTC: four task briefs submitted and returned persistent run directories.
