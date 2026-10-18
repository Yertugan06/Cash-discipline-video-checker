#!/usr/bin/env bash
set -euo pipefail
umask 077
export PATH="$HOME/.local/bin:$PATH"

if [ "$#" -ne 3 ]; then
    echo "Usage: codex-worker {submit|resume|status|result} {1|2} TASK_ID" >&2
    exit 2
fi
operation=$1
slot=$2
task_id=$3
case "$slot" in 1|2) ;; *) echo "Worker slot must be 1 or 2." >&2; exit 2 ;; esac
if [[ ! "$task_id" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$ ]]; then
    echo "Task ID must contain 1-64 letters, numbers, underscores, or hyphens." >&2
    exit 2
fi

pool="$HOME/workspaces/datathon26-workers"
workspace="$pool/worker-$slot"
job_dir="$pool/runs/worker-$slot/$task_id"
self="$HOME/.local/bin/codex-worker"

case "$operation" in
    submit|resume)
        test -d "$workspace/.git" || test -f "$workspace/.git"
        tmux -L codex-workers has-session -t '=implementation'
        task_text=$(cat)
        if [ -z "$task_text" ]; then echo "Task text on stdin is required." >&2; exit 2; fi
        task_text=$(printf '%s\n\n%s' 'Use $ponytail: read ~/.agents/skills/ponytail/SKILL.md. Deliver the smallest complete change with measured benefit; reuse existing code and keep meaningful validation.' "$task_text")
        if [ "$operation" = submit ]; then
            mkdir -p "$(dirname "$job_dir")"
            mkdir "$job_dir"
        else
            case "$(cat "$job_dir/status")" in
                completed|failed) ;;
                *) echo "Only a stopped task can be resumed." >&2; exit 4 ;;
            esac
            thread_id=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline())["thread_id"])' "$job_dir/events.jsonl")
            history_dir="$job_dir/history/$(date -u +%Y%m%dT%H%M%SZ)"
            mkdir -p "$history_dir"
            for artifact in task.txt status exit-code result.md events.jsonl stderr.log runner.log changes.patch git-status.txt untracked.tar.gz base-commit; do
                if [ -f "$job_dir/$artifact" ]; then cp -a "$job_dir/$artifact" "$history_dir/"; fi
            done
            printf '%s\n' "$thread_id" > "$job_dir/resume-thread"
        fi
        printf '%s\n' "$task_text" > "$job_dir/task.txt"
        printf 'queued\n' > "$job_dir/status"
        launch=$(printf '%q ' "$self" _run "$slot" "$task_id")
        launch="$launch >$(printf '%q' "$job_dir/runner.log") 2>&1"
        if ! tmux -L codex-workers new-window -d -t implementation \
            -n "$slot-$task_id" "$launch"; then
            printf 'failed\n' > "$job_dir/status"
            printf '1\n' > "$job_dir/exit-code"
            exit 1
        fi
        printf '%s\n' "$job_dir"
        ;;
    _run)
        trap 'worker_exit=$?; printf "%s\n" "$worker_exit" > "$job_dir/exit-code"; if [ "$worker_exit" -eq 0 ]; then printf "completed\n" > "$job_dir/status"; else printf "failed\n" > "$job_dir/status"; fi' EXIT
        mkdir -p "$pool/locks"
        exec 9>"$pool/locks/worker-$slot.lock"
        flock 9
        printf 'running\n' > "$job_dir/status"
        cd "$workspace"
        if [ -n "$(git status --porcelain)" ] && [ ! -f "$job_dir/resume-thread" ]; then
            echo "Worker has unreviewed changes. Commit reviewed work before submitting another task." >&2
            exit 3
        fi
        source .venv/bin/activate
        export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
        if [ ! -f "$job_dir/base-commit" ]; then git rev-parse HEAD > "$job_dir/base-commit"; fi
        codex_args=(exec --profile implementation --cd "$workspace" --json --output-last-message "$job_dir/result.md")
        if [ -f "$job_dir/resume-thread" ]; then codex_args+=(resume "$(cat "$job_dir/resume-thread")"); fi
        if codex "${codex_args[@]}" - \
            < "$job_dir/task.txt" > "$job_dir/events.jsonl" 2> "$job_dir/stderr.log" 9>&-; then
            agent_exit=0
        else
            agent_exit=$?
        fi
        git diff --binary "$(cat "$job_dir/base-commit")" > "$job_dir/changes.patch"
        git status --porcelain > "$job_dir/git-status.txt"
        git ls-files --others --exclude-standard -z \
            | tar --null -T - -czf "$job_dir/untracked.tar.gz"
        exit "$agent_exit"
        ;;
    status)
        cat "$job_dir/status"
        if [ -f "$job_dir/exit-code" ]; then
            printf 'exit_code='
            cat "$job_dir/exit-code"
        fi
        ;;
    result)
        job_state=$(cat "$job_dir/status")
        case "$job_state" in
            completed|failed) ;;
            *) echo "Task is $job_state; its result is not final." >&2; exit 4 ;;
        esac
        if [ ! -f "$job_dir/result.md" ]; then
            echo "No final agent report. Inspect $job_dir/runner.log and stderr.log." >&2
            exit 1
        fi
        cat "$job_dir/result.md"
        exit "$(cat "$job_dir/exit-code")"
        ;;
    *)
        echo "Unknown operation: $operation" >&2
        exit 2
        ;;
esac
