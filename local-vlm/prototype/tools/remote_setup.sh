#!/usr/bin/env bash
# Разворачивание прототипа на GPU-инстансе Brev (без sudo, всё в ~/forte_proto):
#   Ollama (пользовательский бинарник) + qwen3-vl:4b-instruct, свой venv с torch/transformers для D-FINE.
# Чужие папки не трогает. Запуск: bash remote_setup.sh  (лог: ~/forte_proto/setup.log)
set -u
R=~/forte_proto; mkdir -p "$R"; cd "$R"
exec >> "$R/setup.log" 2>&1
echo "== $(date) setup start"

# 1. Ollama в пользовательской папке
if [ ! -x "$R/ollama/bin/ollama" ]; then
  mkdir -p "$R/ollama"
  curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst -o "$R/ollama.tar.zst"     && tar -C "$R/ollama" --use-compress-program=unzstd -xf "$R/ollama.tar.zst" && rm -f "$R/ollama.tar.zst"
fi
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NUM_PARALLEL=8 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_KEEP_ALIVE=24h \
  OLLAMA_MODELS="$R/ollama_models" nohup "$R/ollama/bin/ollama" serve > "$R/ollama.log" 2>&1 &
  for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 2; done
fi
"$R/ollama/bin/ollama" pull qwen3-vl:4b-instruct && echo "== model ok"

# 2. Свой venv: torch + transformers (D-FINE) + зависимости прототипа
if ! "$R/.venv/bin/python" -m pip --version >/dev/null 2>&1; then     # без python3-venv (нужен sudo): venv без pip + get-pip.py
  rm -rf "$R/.venv"; python3 -m venv --without-pip "$R/.venv" && curl -fsSL https://bootstrap.pypa.io/get-pip.py | "$R/.venv/bin/python" - -q
fi
"$R/.venv/bin/python" -m pip install -q --upgrade pip
"$R/.venv/bin/python" -m pip install -q torch torchvision "transformers>=4.53" pillow numpy fastapi "uvicorn>=0.29" python-multipart openpyxl
"$R/.venv/bin/python" -c "import torch, transformers; print('torch', torch.__version__, torch.cuda.is_available(), 'transformers', transformers.__version__)"
which ffmpeg || echo "!!! ffmpeg not found"
echo "== $(date) SETUP_DONE"
