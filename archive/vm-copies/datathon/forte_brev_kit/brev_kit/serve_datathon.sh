#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/forte_brev_kit/brev_kit
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=2
export VLLM_NO_USAGE_STATS=1
exec .venv/bin/vllm serve /home/ubuntu/forte_brev_kit/models/Qwen3.5-9B \
  --served-model-name Qwen/Qwen3.5-9B \
  --host 127.0.0.1 --port 8010 \
  --max-model-len 16384 --max-num-seqs 8 --max-num-batched-tokens 4096 \
  --gpu-memory-utilization 0.65 --quantization fp8 --enforce-eager \
  --limit-mm-per-prompt '{"image":4,"video":0}' \
  --mm-processor-kwargs '{"max_pixels":589824}' \
  --default-chat-template-kwargs '{"enable_thinking":false}'
