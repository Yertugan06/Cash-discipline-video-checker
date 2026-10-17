#!/usr/bin/env bash
# datathon2 queue B: Addendum B1 probes, after queue A finishes. Weights fetched online once, then cached.
cd ~/dt26-validation; PY=.venv/bin/python; H=validation-evidence/harness; L=validation-evidence/logs
until grep -q D2_QUEUE_DONE $L/d2_queue.txt; do sleep 20; done
for e in dinov2 siglip2; do
  echo "$(date -u +%T) start B1 $e" >> $L/d2_queue.txt
  $PY -I $H/f2_probe.py . $e     > $L/F2_$e.txt 2>&1
  $PY -I $H/f2_probe.py . $e raw > $L/F2_${e}_raw.txt 2>&1
  for p in F2_$e F2_${e}_raw; do $PY -I $H/score.py . $p > $L/score_$p.txt 2>&1; done
done
echo "$(date -u +%T) D2_QUEUE_B_DONE" >> $L/d2_queue.txt
