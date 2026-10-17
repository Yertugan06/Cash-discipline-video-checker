#!/usr/bin/env bash
# Sequential GPU queue (one GPU job at a time). Logs: validation-evidence/logs/<job>.txt
set -u
cd "$(dirname "$0")/../.."
PY=/home/yertugan/.venvs/dt26/bin/python
H=validation-evidence/harness; L=validation-evidence/logs
# wait for any running harness job (anchored, so shells that merely mention a script name don't match)
while pgrep -f "^/home/yertugan/.venvs/dt26/bin/python -I validation-evidence/harness/" >/dev/null; do sleep 10; done
$PY -I $H/f1_rules.py . both cuda           > $L/F1_coco_rules.txt 2>&1
$PY -I $H/verify_windows.py . 4 448         > $L/verify_4fps_s448.txt 2>&1
$PY -I $H/f3_discovery.py . chunk30_2fps_s288 all > $L/F3_chunk30_2fps_s288.txt 2>&1
$PY -I $H/f4_cascade.py . motion_short 5    > $L/F4_motion_short_K5.txt 2>&1
$PY -I $H/f4_cascade.py . uniform10 5       > $L/F4_uniform10_K5.txt 2>&1
echo QUEUE_DONE > $L/queue_done.txt
