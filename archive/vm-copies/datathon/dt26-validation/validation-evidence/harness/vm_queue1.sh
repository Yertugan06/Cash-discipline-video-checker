#!/usr/bin/env bash
# VM queue 1: capacity test (Addendum A1) on the shared L4. One GPU job at a time; each waits for free VRAM.
cd ~/dt26-validation; PY=.venv/bin/python; H=validation-evidence/harness; L=validation-evidence/logs
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
waitfree() { until [ "$(free_mib)" -ge "$1" ]; do sleep 20; done; echo "$(date -u +%T) launch $2 with $(free_mib) MiB free" >> $L/queue1_gpu.txt; }
until grep -q FETCH_DONE $L/fetch_8b.txt; do sleep 15; done
waitfree 13000 q3vl8b_int8
VLM_QUANT=int8 VLM_DIR=~/dt26-validation/models/Qwen3-VL-8B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl8b_int8_4fps_s448 > $L/verify_q3vl8b_int8_4fps_s448.txt 2>&1
waitfree 13000 q25vl7b_int8
VLM_QUANT=int8 VLM_DIR=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/*) $PY -I $H/verify_windows.py . 4 448 q25vl7b_int8_4fps_s448 > $L/verify_q25vl7b_int8_4fps_s448.txt 2>&1
until grep -q FETCH_DONE $L/fetch_4b.txt; do sleep 15; done
waitfree 11500 q3vl4b_bf16
VLM_DIR=~/dt26-validation/models/Qwen3-VL-4B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl4b_L4_4fps_s448 > $L/verify_q3vl4b_L4_4fps_s448.txt 2>&1
echo QUEUE1_DONE > $L/queue1_done.txt
