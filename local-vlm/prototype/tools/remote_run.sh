#!/usr/bin/env bash
# Прогон на GPU-инстансе (после remote_setup.sh):
#   bash remote_run.sh batch <имя> [--only X-1,X-2]   — все видео через batch_eval (трассы, метрики) → ~/forte_proto/runs/<имя>
#   bash remote_run.sh actions                         — эксперимент с действиями по окнам кадров → ~/forte_proto/runs/actions
# Запускается в фоне; лог: ~/forte_proto/runs/<имя>.log
set -u
R=~/forte_proto; mkdir -p "$R/runs"; cd "$R/prototype"
export PYTHONIOENCODING=utf-8 VLM_WORKERS="${VLM_WORKERS:-8}"
MODE="${1:-batch}"; NAME="${2:-run}"; shift 2 || true
VIDEOS="${VIDEOS:-$HOME/data/open/videos}"
case "$MODE" in
  batch)   setsid nohup "$R/.venv/bin/python" batch_eval.py --videos "$VIDEOS" --out "$R/runs/$NAME" "$@" > "$R/runs/$NAME.log" 2>&1 < /dev/null & ;;
  actions) setsid nohup "$R/.venv/bin/python" tools/action_windows.py --videos "$VIDEOS" --out "$R/runs/actions" > "$R/runs/actions.log" 2>&1 < /dev/null & ;;
esac
echo "started $MODE $NAME"
