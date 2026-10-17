#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/forte_brev_kit/brev_kit
export PATH="/home/ubuntu/.local/bin:$PATH"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
stage() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1" | tee run_status.txt; }
trap 'rc=$?; if [ "$rc" -ne 0 ]; then stage "FAILED exit=$rc; see run.log and server.log"; fi' EXIT
stage starting_model
tmux new-session -d -s forte-brev-vlm 'cd /home/ubuntu/forte_brev_kit/brev_kit && bash serve_datathon.sh > server.log 2>&1'
.venv/bin/python - <<'PY'
import json, subprocess, time, urllib.request
for attempt in range(300):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8010/v1/models', timeout=2) as response:
            data = json.load(response)
        assert any(m['id'] == 'Qwen/Qwen3.5-9B' for m in data['data']), data
        print('Local VLM ready on 127.0.0.1:8010')
        break
    except (OSError, ValueError):
        if subprocess.run(['tmux', 'has-session', '-t', 'forte-brev-vlm'], capture_output=True).returncode:
            raise RuntimeError('VLM server exited; see server.log')
        time.sleep(3)
else:
    raise TimeoutError('VLM startup exceeded 15 minutes; see server.log')
PY
stage evaluating_gold
.venv/bin/python scripts/run_vlm.py --gold-frames work/gold_frames/gold_frames.json --base-url http://127.0.0.1:8010/v1 --model Qwen/Qwen3.5-9B --out runs/q35_9b_fp8_gold
.venv/bin/python scripts/eval_states.py --pred runs/q35_9b_fp8_gold/states --gold data/gold_states.csv --out runs/q35_9b_fp8_gold/report_states.md
.venv/bin/python - <<'PY'
import json
meta = json.load(open('runs/q35_9b_fp8_gold/run_meta.json'))
assert meta['videos'], 'No gold predictions'
assert all(v['ok'] == v['frames'] for v in meta['videos'].values()), 'Invalid VLM responses; see gold states'
PY
stage evaluating_videos
.venv/bin/python scripts/run_vlm.py --frames work/frames --base-url http://127.0.0.1:8010/v1 --model Qwen/Qwen3.5-9B --out runs/q35_9b_fp8 --step 1.0 --workers 8
.venv/bin/python - <<'PY'
import csv, json
meta = json.load(open('runs/q35_9b_fp8/run_meta.json'))
expected = {r['video'] for r in csv.DictReader(open('data/videos.csv'), delimiter=';') if not r['duplicate_of']}
assert set(meta['videos']) == expected, 'Missing video predictions'
assert all(v['ok'] == v['frames'] for v in meta['videos'].values()), 'Invalid VLM responses; see states'
PY
.venv/bin/python scripts/timeline_rules.py --states runs/q35_9b_fp8/states --out runs/q35_9b_fp8/violations
.venv/bin/python scripts/eval_videos.py --violations runs/q35_9b_fp8/violations --run-meta runs/q35_9b_fp8/run_meta.json --out runs/q35_9b_fp8/report_videos.md
stage COMPLETE
