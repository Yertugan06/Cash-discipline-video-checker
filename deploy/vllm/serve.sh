#!/usr/bin/env bash
# Serves the perception VLM on 127.0.0.1:8010 for backend.vlm (architecture.md §5, §8).
#
# Model: Qwen3.5-9B FP8 (quantized online from the BF16 checkpoint, see
# architecture.md §5 "18 GiB BF16 checkpoint, quantized online"). This is the
# checkpoint copied VM-to-VM from `datathon` per implementation-plan.md WP2
# step 1; re-download from Hugging Face only if that copy is impossible.
#
# Fallback (documented, NOT active): if the 9B checkpoint or FP8 quantization
# does not fit / load in time, switch to Qwen3-VL-4B (architecture.md §5
# "Fallback L2") by pointing VLM_MODEL_PATH at that checkpoint and dropping
# `--quantization fp8`; this requires a restart (one detector/model per
# deployment, architecture.md §5 "Coexistence").
#
# vLLM version is pinned in requirements-vllm.txt to the exact release that
# produced the q35_9b_fp8 run on `datathon` (vllm==0.31.0; see that run's
# installed-requirements.txt). Install requirements-vllm.txt into its own
# venv before running this script.
set -euo pipefail

VLLM_BIN="${VLLM_BIN:-$(dirname "$0")/../../.venv-vllm/bin/vllm}"
MODEL_PATH="${VLM_MODEL_PATH:?set VLM_MODEL_PATH to the local Qwen3.5-9B checkpoint directory}"
SERVED_MODEL_NAME="${VLM_SERVED_MODEL_NAME:-Qwen/Qwen3.5-9B}"
MAX_MODEL_LEN="${VLM_MAX_MODEL_LEN:-16384}"   # architecture.md §5: "max_model_len 8-16k"
MAX_NUM_SEQS="${VLM_MAX_NUM_SEQS:-16}"        # architecture.md §5: "max_num_seqs 16"
GPU_UTIL="${VLM_GPU_MEMORY_UTILIZATION:-0.80}"  # architecture.md §5: "set util 0.80 ~= 17.6 GiB"

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export DO_NOT_TRACK=1

# Prefix caching is vLLM's default in recent releases, but we pass the flag
# explicitly whenever the installed CLI still exposes it, so a version that
# still defaults it off does not silently lose the lever that makes the fixed
# form prompt cheap (architecture.md §6 lever 1; backend/vlm/client.py puts
# the fixed text first and the image last for exactly this reason).
PREFIX_CACHE_FLAG=()
if "$VLLM_BIN" serve --help 2>/dev/null | grep -q -- '--enable-prefix-caching'; then
  PREFIX_CACHE_FLAG=(--enable-prefix-caching)
fi

# No --enforce-eager: CUDA graphs stay on (architecture.md §6 lever 2).
exec "$VLLM_BIN" serve "$MODEL_PATH" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --host 127.0.0.1 --port 8010 \
  --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --quantization fp8 \
  "${PREFIX_CACHE_FLAG[@]}" \
  --limit-mm-per-prompt '{"image":1,"video":0}' \
  --mm-processor-kwargs '{"max_pixels":589824}' \
  --default-chat-template-kwargs '{"enable_thinking":false}'
