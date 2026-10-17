"""Proposer recall (HX7) and F0 baselines from cached motion signals.

Proposers (no label times, no duration/position priors; per-clip robust z-scores):
  short   : peaks of 1 s-smoothed short-term motion
  state   : peaks of persistent scene-change signal
  mix     : alternate short/state peaks
  uniform : K evenly spaced centres (coverage control; random placement has expected recall = coverage)
Hit = label interval [N, N+1) intersects a window [c-W, c+W].

Also writes prediction files for the scorer:
  F0_always_motion : verdict always violation, events = top-3 'mix' peaks
  F0_motion_thresh : verdict = max state-z above a leave-one-group-out threshold, events = top-3 'mix' peaks
  BLIND_prior      : verdict always violation, t = LOO median(label/duration) x duration (REFERENCE ONLY: position shortcut)
Usage: python -I propose_eval.py <repo_root>
"""
import json, os, statistics as st, sys

import numpy as np

ROOT = sys.argv[1]
P = os.path.join(ROOT, 'data', 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
M = {k: np.load(os.path.join(P, 'motion', k + '.npz')) for k in gt}
os.makedirs(os.path.join(P, 'preds'), exist_ok=True)


def z(x):
    med = np.median(x); mad = np.median(np.abs(x - med)) + 1e-6
    return (x - med) / (1.4826 * mad)


def smooth(x, ts, sec=1.0):
    n = max(1, int(round(sec * len(ts) / max(ts[-1], 1e-6))))
    return np.convolve(x, np.ones(n) / n, mode='same')


def peaks(sig, ts, k, sep):
    order = np.argsort(-sig); out = []
    for i in order:
        if all(abs(ts[i] - c) >= sep for c, _ in out):
            out.append((float(ts[i]), float(sig[i])))
        if len(out) == k:
            break
    return out


def propose(clip, kind, k, w):
    m = M[clip]; ts = m['ts']; dur = float(ts[-1])
    if kind == 'uniform':
        return [((i + 0.5) * dur / k, 0.0) for i in range(k)]
    s = z(smooth(m['short'], ts)); g = z(smooth(m['state'], ts))
    if kind == 'short':
        return peaks(s, ts, k, 2 * w)
    if kind == 'state':
        return peaks(g, ts, k, 2 * w)
    a, b, out = peaks(s, ts, k, 2 * w), peaks(g, ts, k, 2 * w), []
    for x in [v for pair in zip(a, b) for v in pair] + a + b:
        if all(abs(x[0] - c) >= 2 * w for c, _ in out):
            out.append(x)
        if len(out) == k:
            break
    return out


def coverage(c, w, dur):
    grid = np.arange(0, dur, 0.1)
    return float(np.mean(np.any([np.abs(grid - x) <= w for x, _ in c], axis=0))) if c else 0.0


ev = [(k, t) for k, c in gt.items() if c['violation'] for t in c['org_times']]
print(f'events {len(ev)} | clips {len(gt)}')
print('kind     K  W | recall  | mean coverage viol/clean')
for w in (2, 3, 5):
    for kk in (3, 5, 8):
        for kind in ('short', 'state', 'mix', 'uniform'):
            hit = sum(1 for k, t in ev if any(c - w <= t + 1 and t <= c + w for c, _ in propose(k, kind, kk, w)))
            cv = st.mean(coverage(propose(k, kind, kk, w), w, float(M[k]['ts'][-1])) for k in gt if gt[k]['violation'])
            cc = st.mean(coverage(propose(k, kind, kk, w), w, float(M[k]['ts'][-1])) for k in gt if not gt[k]['violation'])
            print(f'{kind:8} {kk:2} {w} | {hit:2}/{len(ev)}   | {cv:.2f} / {cc:.2f}')

# rank of the first window that contains the label, among mix peaks with K=20, W=3
ranks = []
for k, t in ev:
    c = propose(k, 'mix', 20, 3)
    r = next((i + 1 for i, (x, _) in enumerate(c) if x - 3 <= t + 1 and t <= x + 3), None)
    ranks.append(r)
print('mix W=3 rank of first hit (None=miss within 20):', sorted(ranks, key=lambda r: (r is None, r)))

# ---- F0 / blind prediction files -----------------------------------------------------
def ev3(k):
    return [{'t': x, 'code': None, 'conf': s} for x, s in propose(k, 'mix', 3, 3)]

json.dump({k: {'verdict': 'violation', 'events': ev3(k), 'runtime_s': None} for k in gt},
          open(os.path.join(P, 'preds', 'F0_always_motion.json'), 'w'))

feat = {k: float(np.max(z(smooth(M[k]['state'], M[k]['ts'])))) for k in gt}
pred = {}
for k in gt:
    tr = [j for j in gt if gt[j]['group'] != gt[k]['group']]
    best = max(((sum((feat[j] >= th) == gt[j]['violation'] for j in tr), th) for th in (feat[j] for j in tr)))[1]
    v = feat[k] >= best
    pred[k] = {'verdict': 'violation' if v else 'no_violation', 'events': ev3(k) if v else [], 'runtime_s': None}
json.dump(pred, open(os.path.join(P, 'preds', 'F0_motion_thresh.json'), 'w'))

pred = {}
for k in gt:
    dur = float(M[k]['ts'][-1])
    rel = st.median(t / float(M[j]['ts'][-1]) for j in gt if gt[j]['group'] != gt[k]['group'] for t in gt[j]['org_times'])
    pred[k] = {'verdict': 'violation', 'events': [{'t': rel * dur, 'code': None, 'conf': None}], 'runtime_s': None}
json.dump(pred, open(os.path.join(P, 'preds', 'BLIND_prior.json'), 'w'))
print('wrote F0_always_motion, F0_motion_thresh, BLIND_prior')

# ---- F4 proposal files (contract in f4_cascade.py): best motion proposer by the table above = 'short' ---------------
os.makedirs(os.path.join(P, 'proposals'), exist_ok=True)
rt = {k: float(M[k]['wall_time_s']) if 'wall_time_s' in M[k] else None for k in gt}
for name, kind in (('motion_short', 'short'), ('uniform10', 'uniform')):
    out = {'_meta': {'runtime_s': rt if kind != 'uniform' else {}}}
    for k in gt:
        c = propose(k, kind, 10, 4)
        if kind == 'uniform':  # first 5 entries = the evenly spaced K=5 centres, so a top-K cut stays spread
            c = propose(k, kind, 5, 4) + [x for i, x in enumerate(c) if i % 2]
        out[k] = [{'t': t, 'score': s} for t, s in c]
    json.dump(out, open(os.path.join(P, 'proposals', name + '.json'), 'w'))
print('wrote proposals motion_short, uniform10')
