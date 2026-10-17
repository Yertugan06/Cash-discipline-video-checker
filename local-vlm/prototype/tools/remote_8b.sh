#!/usr/bin/env bash
# Тест 8B на вопросах о действиях (после перезапуска инстанса): поднимает Ollama, тянет qwen3-vl:8b-instruct,
# гоняет client_leave ask + action_windows. Лог: ~/forte_proto/runs/run8b.log, итог — строка ALL8B_DONE.
set -u
R=~/forte_proto; cd "$R"; mkdir -p runs
exec >> runs/run8b.log 2>&1
echo "== $(date) start; RAM: $(free -g | awk '/Mem/ {print $2" GB, free "$7" GB"}')"
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NUM_PARALLEL=4 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_KEEP_ALIVE=24h \
  OLLAMA_MODELS="$R/ollama_models" setsid nohup "$R/ollama/bin/ollama" serve > "$R/ollama.log" 2>&1 < /dev/null &
  for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 2; done
fi
OLLAMA_HOST=127.0.0.1:11434 "$R/ollama/bin/ollama" pull qwen3-vl:8b-instruct 2>&1 | tail -2
cd prototype
export PYTHONIOENCODING=utf-8 DETECTOR=0 VLM_MODEL=qwen3-vl:8b-instruct VLM_WORKERS=2
../.venv/bin/python tools/client_leave.py ask --videos ~/data/open/videos --cand ../runs/leave_candidates.json --out ../runs/leave_answers_8b.json
mkdir -p ../runs/actions8b
../.venv/bin/python tools/action_windows.py --videos ~/data/open/videos --out ../runs/actions8b
nvidia-smi --query-gpu=memory.used --format=csv,noheader
echo "== $(date) ALL8B_DONE"
