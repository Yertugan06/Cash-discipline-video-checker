#!/usr/bin/env bash
# Всё одной командой на инстансе Brev (терминал JupyterLab или brev shell).
#   bash run_on_brev.sh                               # Ollama + qwen3-vl:4b — тот же квант, что на ноутбуках (по умолчанию)
#   bash run_on_brev.sh ollama qwen3.5:4b             # сравнить с Qwen3.5-4B
#   bash run_on_brev.sh ollama qwen3-vl:2b            # самая быстрая
#   bash run_on_brev.sh vllm Qwen/Qwen3-VL-4B-Instruct   # та же модель без квантования (bf16) — оценить потерю от кванта
#   STAGE=all bash run_on_brev.sh ...                 # + все видео → правила → метрики как у жюри
# Модель работает ЛОКАЛЬНО на этой машине (127.0.0.1). Облачные AI-API не используются.
set -euo pipefail
cd "$(dirname "$0")"
KIT="$(pwd)"; VIDEOS="${VIDEOS:-$KIT/../videos}"; MODELS_DIR="${MODELS_DIR:-$HOME/models}"
BACKEND="${1:-ollama}"; MODEL="${2:-qwen3-vl:4b-instruct}"; STAGE="${STAGE:-gold}"; STEP="${STEP:-1.0}"; WORKERS="${WORKERS:-4}"
TAG="$(echo "$BACKEND-$MODEL" | tr 'A-Z:./' 'a-z___')"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
SUDO=""; if [ "$(id -u)" != "0" ]; then SUDO="sudo"; fi

# 0) системное: ffmpeg
command -v ffmpeg >/dev/null || { $SUDO apt-get update -y && $SUDO apt-get install -y ffmpeg; }
python3 -m pip install -q --user pillow requests 2>/dev/null || python3 -m pip install -q pillow requests

if [ "$BACKEND" = "ollama" ]; then
  # 1) Ollama (MIT) — локальный сервер на 127.0.0.1:11434
  command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
  if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
    OLLAMA_NUM_PARALLEL="$WORKERS" nohup ollama serve > "$KIT/ollama.log" 2>&1 &
    for i in $(seq 1 30); do curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 2; done
  fi
  echo ">>> $(ollama --version)"
  ollama pull "$MODEL"
  RUN_ARGS=(--model "$MODEL" --structured ollama --base-url http://127.0.0.1:11434)
else
  # 1) vLLM — сервер на 127.0.0.1:8000 (bf16, для сравнения с квантованной версией)
  if [ ! -x "$HOME/venv/bin/vllm" ]; then
    python3 -m venv "$HOME/venv"; "$HOME/venv/bin/pip" install -U pip
    "$HOME/venv/bin/pip" install vllm pillow requests "huggingface_hub[cli]"
  fi
  source "$HOME/venv/bin/activate"; NAME="$(basename "$MODEL")"
  if [ ! -d "$MODELS_DIR/$NAME" ]; then
    mkdir -p "$MODELS_DIR"
    if command -v hf >/dev/null 2>&1; then hf download "$MODEL" --local-dir "$MODELS_DIR/$NAME"
    else huggingface-cli download "$MODEL" --local-dir "$MODELS_DIR/$NAME"; fi
  fi
  if ! curl -sf http://127.0.0.1:8000/v1/models >/dev/null; then
    start_server () {
      nohup vllm serve "$MODELS_DIR/$NAME" --served-model-name "$MODEL" --host 127.0.0.1 --port 8000 \
        --max-model-len 16384 --gpu-memory-utilization 0.85 --limit-mm-per-prompt "$1" > "$KIT/vllm.log" 2>&1 &
      echo $! > "$KIT/vllm.pid"
    }
    start_server '{"image": 4}'; RETRIED=""
    echo ">>> жду запуска vLLM (лог: $KIT/vllm.log)…"
    for i in $(seq 1 120); do
      curl -sf http://127.0.0.1:8000/v1/models >/dev/null && break
      if ! kill -0 "$(cat "$KIT/vllm.pid")" 2>/dev/null; then
        if grep -qi "limit.mm.per.prompt" "$KIT/vllm.log" && [ -z "$RETRIED" ]; then RETRIED=1; start_server 'image=4'; continue; fi
        echo "!!! vLLM упал:"; tail -n 30 "$KIT/vllm.log"; exit 1
      fi
      sleep 10
    done
  fi
  RUN_ARGS=(--model "$MODEL" --structured json_schema --base-url http://127.0.0.1:8000/v1)
fi

# 2) этап 1 — анкета на золотых кадрах
[ -f work/gold_frames/gold_frames.json ] || python3 scripts/extract_frames.py --videos "$VIDEOS" --out work/gold_frames --gold data/gold_states.csv
python3 scripts/run_vlm.py --gold-frames work/gold_frames/gold_frames.json "${RUN_ARGS[@]}" --out "runs/${TAG}_gold" --workers "$WORKERS"
python3 scripts/eval_states.py --pred "runs/${TAG}_gold/states" --gold data/gold_states.csv --out "runs/${TAG}_gold/report_states.md" | head -30

# 3) этап 2 — все видео (STAGE=all)
if [ "$STAGE" = "all" ]; then
  [ -f work/frames/X-1/frames.json ] || python3 scripts/extract_frames.py --videos "$VIDEOS" --out work/frames --fps 2
  python3 scripts/run_vlm.py --frames work/frames "${RUN_ARGS[@]}" --out "runs/$TAG" --step "$STEP" --workers "$WORKERS"
  python3 scripts/timeline_rules.py --states "runs/$TAG/states" --out "runs/$TAG/violations"
  python3 scripts/eval_videos.py --violations "runs/$TAG/violations" --run-meta "runs/$TAG/run_meta.json" --out "runs/$TAG/report_videos.md" | head -40
fi
echo ">>> Готово. Отчёты в runs/${TAG}_gold/ $( [ "$STAGE" = all ] && echo "и runs/$TAG/" )"
