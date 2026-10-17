#!/usr/bin/env bash
# Прогон с промптом v2 на уже запущенном сервере модели (vLLM на :8000 или Ollama на :11434).
#   bash stage_v2.sh                 # этап 1: золотые кадры, max_side 1024
#   bash stage_v2.sh gold 1280       # то же, картинки крупнее (ключ в замке, деньги на столе)
#   bash stage_v2.sh all 1024        # + все 40 видео → правила → метрики как у жюри
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:-gold}"; SIDE="${2:-1024}"; WORKERS="${WORKERS:-8}"; STEP="${STEP:-1.0}"; PROMPTS="${PROMPTS:-prompts_v2}"
# Python с pillow/requests: .venv рядом со скриптом → ~/venv → системный
if [ -z "${PY:-}" ]; then
  for c in "$PWD/.venv/bin/python" "$HOME/venv/bin/python"; do [ -x "$c" ] && PY="$c" && break; done
  PY="${PY:-$(command -v python3 || command -v python)}"
fi

# Сервер модели: BASE из окружения, иначе ищем vLLM на 8010/8000/8001, иначе Ollama на 11434
if [ -z "${BASE:-}" ]; then
  for p in 8010 8000 8001; do
    if curl -sf "http://127.0.0.1:$p/v1/models" >/dev/null; then BASE="http://127.0.0.1:$p/v1"; break; fi
  done
fi
if [ -n "${BASE:-}" ] && [ "${BASE%/v1}" != "$BASE" ]; then
  STRUCT=json_schema
  MODEL="${MODEL:-$(curl -s "$BASE/models" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])')}"
elif curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  BASE=http://127.0.0.1:11434; STRUCT=ollama; MODEL="${MODEL:-qwen3-vl:4b-instruct}"
else
  echo "!!! Сервер модели не найден (vLLM :8010/:8000/:8001 или Ollama :11434). Задайте BASE=http://127.0.0.1:ПОРТ/v1"; exit 1
fi
TAG="$(echo "$MODEL" | tr 'A-Z:./' 'a-z___')_$(basename "$PROMPTS")_${SIDE}"
echo ">>> модель $MODEL ($STRUCT), промпт $PROMPTS, max_side $SIDE, workers $WORKERS"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader || true

[ -f work/gold_frames/gold_frames.json ] || "$PY" scripts/extract_frames.py --videos ../videos --out work/gold_frames --gold data/gold_states.csv
"$PY" scripts/run_vlm.py --gold-frames work/gold_frames/gold_frames.json --model "$MODEL" --structured "$STRUCT" --base-url "$BASE" \
  --prompts "$PROMPTS" --max-side "$SIDE" --workers "$WORKERS" --out "runs/${TAG}_gold"
"$PY" scripts/eval_states.py --pred "runs/${TAG}_gold/states" --gold data/gold_states.csv --out "runs/${TAG}_gold/report_states.md"

if [ "$MODE" = "all" ]; then
  [ -f work/frames/X-1/frames.json ] || "$PY" scripts/extract_frames.py --videos ../videos --out work/frames --fps 2
  "$PY" scripts/run_vlm.py --frames work/frames --model "$MODEL" --structured "$STRUCT" --base-url "$BASE" \
    --prompts "$PROMPTS" --max-side "$SIDE" --workers "$WORKERS" --step "$STEP" --out "runs/$TAG"
  "$PY" scripts/timeline_rules.py --states "runs/$TAG/states" --out "runs/$TAG/violations"
  "$PY" scripts/eval_videos.py --violations "runs/$TAG/violations" --run-meta "runs/$TAG/run_meta.json" --out "runs/$TAG/report_videos.md"
fi
echo ">>> Отчёты: runs/${TAG}_gold/report_states.md $( [ "$MODE" = all ] && echo "и runs/$TAG/report_videos.md" )"
