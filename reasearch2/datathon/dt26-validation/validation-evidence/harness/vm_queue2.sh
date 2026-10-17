#!/usr/bin/env bash
# VM queue 2: Addendum A2 per-item prompt, dev split only. Starts after queue 1.
cd ~/dt26-validation; PY=.venv/bin/python; H=validation-evidence/harness; L=validation-evidence/logs
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
waitfree() { until [ "$(free_mib)" -ge "$1" ]; do sleep 20; done; echo "$(date -u +%T) launch $2 with $(free_mib) MiB free" >> $L/queue2_gpu.txt; }
until [ -f $L/queue1_done.txt ]; do sleep 20; done
waitfree 11500 q3vl4b_items_dev
VLM_DIR=~/dt26-validation/models/Qwen3-VL-4B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl4b_items_dev items dev > $L/verify_q3vl4b_items_dev.txt 2>&1
waitfree 13000 q3vl8b_int8_items_dev
VLM_QUANT=int8 VLM_DIR=~/dt26-validation/models/Qwen3-VL-8B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl8b_int8_items_dev items dev > $L/verify_q3vl8b_int8_items_dev.txt 2>&1
echo QUEUE2_DONE > $L/queue2_done.txt
