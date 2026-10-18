# Remote implementation workers

The user and one orchestrator choose tasks and file ownership. The orchestrator sends
tasks over SSH to four independent Codex workers, collects their reports and code,
reviews and integrates the results, then assigns the next batch.

| Worker | VM | Slot | Git worktree |
| --- | --- | --- | --- |
| D2-1 | datathon2 | 1 | `~/workspaces/datathon26-workers/worker-1` |
| D2-2 | datathon2 | 2 | `~/workspaces/datathon26-workers/worker-2` |
| D3-1 | datathon3 | 1 | `~/workspaces/datathon26-workers/worker-1` |
| D3-2 | datathon3 | 2 | `~/workspaces/datathon26-workers/worker-2` |

All four start from committed main `7bc47e71cbab37a74b2ebce82ac790d6b5111b45`.
Branches are `implementation/<VM>-worker-<slot>` in each VM's
`~/workspaces/datathon26-workers/repo.git`. Local uncommitted application work was
not included in this baseline. Agree on a new common base before moving worker branches.

Each worktree has its own Python 3.12 virtual environment, CUDA 12.8 PyTorch, and
frontend dependencies. Codex uses the `implementation` profile in
`~/.codex/implementation.config.toml`, inheriting the configured model and Context7.
Nested agents are disabled. A per-slot file lock permits two active managed workers
per VM; additional tasks for the same slot wait for that slot's lock.

## Submit and collect

Install source: [`scripts/remote_codex_worker.sh`](../scripts/remote_codex_worker.sh).
It is installed as `~/.local/bin/codex-worker` on both VMs.

Put a task brief in a text file. Include the goal, owned files, acceptance criteria,
required checks, and any dependency on another worker's result.

```bash
ssh -T datathon2 '~/.local/bin/codex-worker submit 1 task-001' < task.md
ssh -T datathon2 '~/.local/bin/codex-worker status 1 task-001'
ssh -T datathon2 '~/.local/bin/codex-worker result 1 task-001'
```

To continue an explicitly stopped/completed task without losing its thread or uncommitted work,
use `codex-worker resume SLOT TASK_ID` with the follow-up on stdin. It archives the previous run
artifacts under `history/<UTC time>/`, resumes the exact thread, and keeps the original patch base.
It refuses a task still running. The current implementation profile uses the user's requested
Fast service tier; new submissions and resumes explicitly invoke the installed Ponytail skill.

Choose `datathon2` or `datathon3` and slot `1` or `2`. Task IDs must be unique per slot
and contain 1–64 letters, numbers, underscores, or hyphens. Submission returns the
remote result directory immediately; execution continues under tmux after SSH disconnects.

States are `queued`, `running`, `completed`, or `failed`. `completed` means the Codex
process exited successfully; the orchestrator must review actual test results before
accepting the implementation. Failed runs preserve their logs and exit code.

Results are stored in
`~/workspaces/datathon26-workers/runs/worker-<slot>/<task-id>/`:

- `result.md`: the worker's final report.
- `changes.patch`: tracked changes relative to the task's starting commit.
- `untracked.tar.gz`: new files that are not ignored by Git.
- `git-status.txt` and `base-commit`: source state for review.
- `events.jsonl`: Codex events, including its thread ID.
- `stderr.log`, `runner.log`, `status`, and `exit-code`: execution diagnostics.

```bash
rsync -az datathon2:workspaces/datathon26-workers/runs/worker-1/task-001/ ./worker-results/d2-1-task-001/
```

Review the patch and new-file archive before integration. The launcher does not merge
or commit application changes. Commit reviewed work on the worker branch before
assigning its next task: a worker with unreviewed changes refuses another task.

The implementation runs, builds, and tests execute on the selected VM. The orchestrator
can remain on the laptop and manage SSH, task briefs, review, and integration.
Codex's built-in subagent tools do not distribute workers between VMs automatically.

## Inspect the workers

```bash
ssh -t datathon2 'tmux -L codex-workers attach -t implementation'
ssh -t datathon3 'tmux -L codex-workers attach -t implementation'
```

Detach with Ctrl-b, then d. The two persistent shell windows are available for each
worktree; submitted tasks use separate temporary windows on the same tmux server.

The slot lock is held by the task launcher, not inherited by Codex's background server.
This lets the slot accept another task after a run finishes.

## GPU work and approvals

Both workers on a VM share its single L4. Run one GPU-heavy experiment at a time,
coordinating through `~/.cache/datathon-workers/gpu.lock`.
CUDA is verified in each worktree's VM environment. NVIDIA devices are hidden inside
Codex's filesystem sandbox; the orchestrator handles approved GPU commands separately
when a worker reports that boundary. Workers must report checks they could not run.

Codex sign-in was completed separately on each VM through device login.

Protocol reference: [Codex CLI](https://learn.chatgpt.com/docs/cli/reference), including
`codex exec --json` and `--output-last-message` for downstream results.
