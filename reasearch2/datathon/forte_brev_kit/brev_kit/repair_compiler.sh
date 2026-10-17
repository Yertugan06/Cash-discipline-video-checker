#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/forte_brev_kit/brev_kit
export PYTHONUNBUFFERED=1
printf '%s installing_build_tools\n' "$(date -u +%FT%TZ)" | tee run_status.txt
sudo -n apt-get install -y build-essential
.venv/bin/python -c 'from triton.runtime import driver; print("Triton compiler and CUDA driver verified; GPU:", driver.active.get_current_device())'
exec bash run_evaluation.sh
