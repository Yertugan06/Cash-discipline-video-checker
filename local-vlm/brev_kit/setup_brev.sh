#!/usr/bin/env bash
# Подготовка GPU-машины Brev (Ubuntu). Запуск:  bash setup_brev.sh Qwen/Qwen3.5-9B
# ВАЖНО: модель работает ЛОКАЛЬНО на этой машине. Никаких облачных API (в т.ч. размещённых NVIDIA NIM / build.nvidia.com).
set -euo pipefail
MODEL="${1:-Qwen/Qwen3.5-9B}"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"

sudo apt-get update -y && sudo apt-get install -y ffmpeg
python3 -m venv "$HOME/venv" && source "$HOME/venv/bin/activate"
pip install -U pip
pip install vllm pillow requests sentence-transformers "huggingface_hub[cli]"

# Веса скачиваются ОДИН раз (это не «облачный AI-сервис»: дальше модель работает офлайн)
mkdir -p "$MODELS_DIR"
if command -v hf >/dev/null 2>&1; then hf download "$MODEL" --local-dir "$MODELS_DIR/$(basename "$MODEL")";
else huggingface-cli download "$MODEL" --local-dir "$MODELS_DIR/$(basename "$MODEL")"; fi
# эмбеддер для открытого мира (опционально)
if command -v hf >/dev/null 2>&1; then hf download BAAI/bge-m3 --local-dir "$MODELS_DIR/bge-m3"; fi

nvidia-smi
echo "Готово. Запуск сервера (в отдельном терминале/tmux):"
echo "  source ~/venv/bin/activate"
echo "  vllm serve $MODELS_DIR/$(basename "$MODEL") --served-model-name $MODEL --host 127.0.0.1 --port 8000 \\"
echo "       --max-model-len 16384 --gpu-memory-utilization 0.90 --limit-mm-per-prompt '{\"image\": 4}'"
echo "  (в старых версиях vLLM: --limit-mm-per-prompt image=4)"
