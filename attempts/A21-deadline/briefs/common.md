# A21 shared contract — deadline implementation, 2026-10-18

User explicitly switched from design grilling to implementation with four remote workers and
3.5 hours remaining at 02:41 UTC (target finish before 06:05 UTC). Produce first useful results
within 30–40 minutes; report concrete blockers early in `attempts/A21-deadline/progress-<owner>.md`.
The orchestrator owns review, integration, real GPU runs and final validation. No nested agents.

User steering: use **$ponytail**, full level, from `~/.agents/skills/ponytail/SKILL.md` on the VM.
Choose the smallest complete implementation with measured value. Reuse helpers, avoid frameworks,
dependency churn, speculative interfaces and large rewrites. Keep validation for the actual risks.
First return a useful runnable slice; additional work needs evidence that it solves a remaining gap.

All workers start committed main `7bc47e7`. The orchestrator has extra uncommitted annotation/UI
and optional desk-history work; do not overwrite that during integration. Own only assigned files.
Do not edit shared CONTEXT.md, global README, dependency locks, knowledge rules or other workers'
files. Do not commit; launcher returns patches/new files for review. Use existing code/helpers.

Dataset videos/frames must NEVER enter cloud AI context. No view_image, browser screenshots,
base64 output, remote vision APIs, or reading image bytes into tool text. Read numeric/text
caches and run actual local models on the VM. Report actual tests/runs; never invent output.
No secrets in reports. Offline weights only. No new paid instances or interfering with services.

GPU: one heavy job per VM, coordinated with `~/.cache/datathon-workers/gpu.lock`. If your Codex
sandbox blocks CUDA or network, do CPU tests, write a concrete runnable script plus argv JSON
and `GPU_RUN_READY` in your progress report; the orchestrator will inspect/run it outside sandbox.
Do not waste time retrying GPU permissions. Existing worktree `.venv` is provisioned. Discover
local weights/cache/video paths read-only under ~/data, ~/dt26-validation, ~/agentA-rulebook,
~/datathon26-annotation-preview (datathon2), ~/workspaces/datathon26 (datathon3). No downloads.

Current baseline 32/40 (0 clean FP, 8 missed) is NOT trusted reason validation. Prior A18/A19 blob
history heuristics failed. No filename, outfit, setup-position or timestamp hacks; no retuning on
all public outcomes. Use RULE_SCOPE=detector for experiments; legal citations remain pending.

Confirmed HUMAN observations (not machine/organizer reason ground truth):
- One fixed camera, multiple table/equipment setups and scenario groups. No cross-file cash history.
- X4 and X47 are byte duplicates, different organizer markers 57/68 s. First client shows ID, pays,
  cash is counted, records entered, ID returned, client leaves; cash remains on desk. Client2 touches
  door at55s, is inside closing at57s while old cash remains. Client2 shows ID FIRST then pays;
  cashier puts new cash directly ON TOP of old cash, then uses laptop. Exact stacking time unknown.
  Supported mechanisms: previous-session cash at next entry, then cash combination. Current
  C-ID-BEFORE-CASH@66 is unsupported. No moving a wrong-rule hit to57 to improve timing.
- Clean X5/X48 and X39 store cash between clients. X38 leaves previous cash at new client.
- Clean X19 first client gives cash without ID observed; second client shows ID. Blanket physical
  ID-first rule applicability is unverified. Recognition miss alone cannot prove non-presentation.
- X1 counter accepts all notes as valid, cashier visibly hand-counts/returns some near official22s.
  Violation CAUSE UNRESOLVED. Never invent counterfeit/rejected/off-camera/manual-count prohibition.
- X20 takes cash from safe, leaves safe open then counts. No room exit described: current
  L-NO-DOCS-ON-LEAVE@1 is unsupported. Room exit != walking to safe/equipment.
- X43/X45 stop after counting/checking; never infer future cash abandonment from recording cutoff.
- X22 key left after cashier exit; X44 rejected notes recombined without detector check. Those
  capabilities are unimplemented/disabled; don't claim perception fixes alone enable them.

Local A13 numeric re-score: seven cash-positive frames, four negatives. OWLv2 TP0/FN7/TN4/FP0;
GDINO TP1/FN6/TN3/FP1; Qwen2.5VL7B TP0/FN7/TN4/FP0. Historical4/11 is accuracy, NOT cash recall.
A13 gold has frame-presence labels, no object boxes, one positive and one negative ID frame.

Shared boundary: worker D3-1 owns Context and rules/events. Add optional trailing
`visual_checks: list[dict] | None = None` to Context if needed, so existing positional callers work.
Worker D2-2 owns verifier production integration. Evidence records use
`{family,t,box,answer,ok,source,question_id}`; family door/laptop/safe/desk_cash/id; answer is explicit
state or unknown, box normalized, source identifies actual model. Unknown/failure NEVER means no.
Only directly supported state answers may refine observations; no invented cash boxes/owners from
yes/no presence. ID non-presentation requires adequate interval visibility, not a few negative stills.

Meaningful tests include positive, clean twin, occlusion/cutoff and invalid/model-unavailable paths.
Use Context7 for current library/API usage per AGENTS. Report changed files, exact test results,
commands for any unrun GPU work, measured limits and integration notes. Do not call work complete
merely because tests mock inference. Produce code/diagnostic artifacts within your assigned scope.
