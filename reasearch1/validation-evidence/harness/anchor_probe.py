"""Anchor probe (architecture stage, 2026-10-17): do labelled events coincide with person-presence transitions?

Pre-registered before running, on the cached F1 detections (RT-DETR v2 r18, 2 fps, full frame; no new inference).
  person count per frame = boxes of class person with score >= 0.5; median-filtered over 3 frames (1.5 s)
  anchor = a frame where the filtered count differs from the previous frame (someone enters or leaves the view)
  hit    = label interval [N, N+1) intersects [anchor - W, anchor + W], W in {1, 2, 3} s  (same rule as propose_eval.py)
Controls, same clips:
  density-matched random: n_anchors(clip) uniform-random times, 2000 draws (expected coverage, no position prior)
  clean vs violation: anchors per minute (anchors are candidates, not a verdict signal)
Bar: anchor hit-rate at +-2 s beats density-matched random by >= 4 events of 22 -> anchors are a useful
localization skeleton. Otherwise the anchor design gets no localization credit.
Prints aggregates only.  Usage: python -I anchor_probe.py <repo_root>
"""
import json, os, sys

import numpy as np

ROOT = sys.argv[1]
P = os.path.join(ROOT, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
rng = np.random.default_rng(26)


def anchors(k):
    a = np.load(os.path.join(P, 'f1_dets', k + '.npy'))
    ts = np.unique(a[a[:, 1] == -1, 0])
    cnt = np.array([int(((a[:, 0] == t) & (a[:, 1] == 0) & (a[:, 2] >= 0.5)).sum()) for t in ts])
    f = np.array([np.median(cnt[max(0, i - 1):i + 2]) for i in range(len(cnt))])
    return ts, [float(ts[i]) for i in range(1, len(f)) if f[i] != f[i - 1]]


def hit(cands, n, w):
    return any(c + w >= n and c - w < n + 1 for c in cands)


res = {w: [0, []] for w in (1, 2, 3)}
rate = {True: [], False: []}
for k, c in gt.items():
    ts, an = anchors(k)
    dur = float(ts[-1])
    rate[bool(c['violation'])].append(60 * len(an) / max(dur, 1))
    for n in c['org_times']:
        for w in res:
            res[w][0] += hit(an, n, w)
            draws = rng.uniform(0, dur, size=(2000, max(len(an), 1)))
            res[w][1].append(np.mean([hit(d, n, w) for d in draws]) if an else 0.0)

n_ev = sum(len(c['org_times']) for c in gt.values())
print(f'events {n_ev} | anchors/min violation median {np.median(rate[True]):.1f} '
      f'(range {min(rate[True]):.1f}-{max(rate[True]):.1f}) | clean median {np.median(rate[False]):.1f} '
      f'(range {min(rate[False]):.1f}-{max(rate[False]):.1f})')
for w, (h, exp) in res.items():
    print(f'+-{w}s: anchor hits {h}/{n_ev} | density-matched random expected {sum(exp):.1f}/{n_ev}')
