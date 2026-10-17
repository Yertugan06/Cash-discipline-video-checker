#!/usr/bin/env bash
# datathon2 queue (dedicated L4, bf16): A1 capacity test, cross-machine 4B reproduction, A2 per-item prompt (dev).
cd ~/dt26-validation; PY=.venv/bin/python; H=validation-evidence/harness; L=validation-evidence/logs
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
VIDMD5=$(cat validation-evidence/videos.md5)
until grep -q VENV_DONE $L/venv.txt; do sleep 15; done
until [ "$(cd ~/data/open/videos && ls *.mov 2>/dev/null | wc -l)" -eq 42 ] && [ "$(cd ~/data/open/videos && md5sum *.mov | sort | md5sum | cut -d' ' -f1)" = "$VIDMD5" ]; do sleep 20; done
echo "$(date -u +%T) videos verified" >> $L/d2_queue.txt
run() { echo "$(date -u +%T) start $1" >> $L/d2_queue.txt; shift; "$@"; echo "$(date -u +%T) end rc=$?" >> $L/d2_queue.txt; }
until grep -q FETCH_DONE $L/fetch_8b.txt; do sleep 15; done
run A1_8b env VLM_DIR=$HOME/dt26-validation/models/Qwen3-VL-8B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl8b_4fps_s448 > $L/verify_q3vl8b_4fps_s448.txt 2>&1
until grep -q FETCH_DONE $L/fetch_4b.txt; do sleep 15; done
run A1c_4b_L4 env VLM_DIR=$HOME/dt26-validation/models/Qwen3-VL-4B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl4b_L4_4fps_s448 > $L/verify_q3vl4b_L4_4fps_s448.txt 2>&1
run A2_4b_items_dev env VLM_DIR=$HOME/dt26-validation/models/Qwen3-VL-4B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl4b_items_dev items dev > $L/verify_q3vl4b_items_dev.txt 2>&1
run A2_8b_items_dev env VLM_DIR=$HOME/dt26-validation/models/Qwen3-VL-8B-Instruct $PY -I $H/verify_windows.py . 4 448 q3vl8b_items_dev items dev > $L/verify_q3vl8b_items_dev.txt 2>&1
echo D2_QUEUE_DONE >> $L/d2_queue.txt
