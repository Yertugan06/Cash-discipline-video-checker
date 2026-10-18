#!/usr/bin/env bash
set -euo pipefail
# Existing environments only; no installation, network lookup or dependency mutation.
safe_probe_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
for safe_probe_python in \
  "${SAFE_PROBE_PYTHON:-/home/ubuntu/workspaces/datathon26/.venv/bin/python}" \
  /home/ubuntu/dt26-validation/.venv/bin/python \
  /home/ubuntu/.venv/bin/python \
  /home/ubuntu/workspaces/datathon26-workers/worker-1/.venv/bin/python; do
  if test -x "$safe_probe_python" && "$safe_probe_python" -c \
    'import importlib.metadata as m; assert int(m.version("transformers").split(".")[0]) >= 5; m.version("accelerate"); m.version("torch")' \
    >/dev/null 2>&1; then
    printf 'Using existing local ML Python: %s\n' "$safe_probe_python"
    exec "$safe_probe_python" "$safe_probe_dir/pilot.py" "$@"
  fi
done
printf '%s\n' 'No compatible existing ML Python found. Set SAFE_PROBE_PYTHON explicitly; nothing installed.' >&2
exit 2
