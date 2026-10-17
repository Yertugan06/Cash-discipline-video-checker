#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/forte_brev_kit/brev_kit
export PATH="/home/ubuntu/.local/bin:$PATH"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
stage() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1" | tee run_status.txt; }
trap 'rc=$?; if [ "$rc" -ne 0 ]; then stage "FAILED exit=$rc; see run.log and server.log"; fi' EXIT
stage installing
sudo -n apt-get update -y
sudo -n apt-get install -y ffmpeg build-essential
uv venv --python /home/ubuntu/.local/bin/python3.12 .venv
uv pip install --python .venv/bin/python vllm pillow requests --torch-backend=auto
.venv/bin/python -c 'import importlib.metadata as m; print({p:m.version(p) for p in ("vllm","torch","transformers","pillow","huggingface-hub")})'
uv pip freeze --python .venv/bin/python > installed-requirements.txt
stage downloading_model
.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3.5-9B', local_dir='/home/ubuntu/forte_brev_kit/models/Qwen3.5-9B')
PY
stage checking_scripts
.venv/bin/python -m compileall -q scripts tests
.venv/bin/python tests/make_fixture_states.py work/fixture_states
.venv/bin/python scripts/timeline_rules.py --states work/fixture_states --out work/fixture_violations
.venv/bin/python - <<'PY'
import json
from pathlib import Path
base = Path('work/fixture_violations')
for video, expected in {'X-26': 'leave_cash', 'X-28': 'leave_laptop'}.items():
    rows = json.loads((base / f'{video}.json').read_text())['violations']
    assert any(v['rule'] == expected for v in rows), (video, rows)
for video in ('X-27', 'X-29'):
    rows = json.loads((base / f'{video}.json').read_text())['violations']
    assert not rows, (video, rows)
print('Fixture checks passed: positive and negative cases.')
PY
stage extracting_frames
.venv/bin/python scripts/extract_frames.py --videos ../videos --out work/gold_frames --gold data/gold_states.csv
.venv/bin/python scripts/extract_frames.py --videos ../videos --out work/frames --fps 2
.venv/bin/python - <<'PY'
import csv, json
from pathlib import Path
gold = list(csv.DictReader(open('data/gold_states.csv'), delimiter=';'))
expected = {(r['video'], float(r['t'])) for r in gold}
actual = {(r['video'], r['t']) for r in json.load(open('work/gold_frames/gold_frames.json'))['frames']}
assert actual == expected, ('gold frames missing', expected - actual)
videos = list(csv.DictReader(open('data/videos.csv'), delimiter=';'))
expected_videos = {r['video'] for r in videos if not r['duplicate_of']}
actual_videos = {json.loads(p.read_text())['video'] for p in Path('work/frames').glob('*/frames.json')}
assert expected_videos == actual_videos, (expected_videos - actual_videos, actual_videos - expected_videos)
print(f'Validated {len(actual)} gold frames and {len(actual_videos)} unique videos.')
PY
exec bash run_evaluation.sh
