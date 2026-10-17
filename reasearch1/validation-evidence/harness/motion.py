"""Cheap, camera-agnostic motion signals for every clip (no zones, no learned parameters).

Per sampled frame (~SAMPLE_FPS, timestamps from container PTS because clips are VFR):
  short : mean |frame_t - frame_{t-1}| on a blurred 116x212 grayscale frame (activity)
  state : mean |frame_t - median(frames in [t-8s, t-4s])|   (persistent scene change: object left/removed, door, person gone)
Cached to data/validation-private/motion/<clip>.npz. Prints timing aggregates only.
Usage: python -I motion.py <repo_root>
"""
import json, os, sys, time

import av
import cv2
import numpy as np

ROOT = sys.argv[1]
P = os.path.join(ROOT, 'data', 'validation-private')
OUT = os.path.join(P, 'motion'); os.makedirs(OUT, exist_ok=True)
SAMPLE_FPS = 5.0
gt = json.load(open(os.path.join(P, 'gt.json')))


def signals(path):
    ts, frames = [], []
    with av.open(path) as c:
        s = c.streams.video[0]; s.thread_type = 'AUTO'
        nxt = 0.0
        for f in c.decode(s):
            t = float(f.pts * s.time_base)
            if t + 1e-6 < nxt:
                continue
            nxt = t + 1.0 / SAMPLE_FPS
            g = f.to_ndarray(format='gray')
            g = cv2.resize(g, (g.shape[1] // 4, g.shape[0] // 4), interpolation=cv2.INTER_AREA)
            frames.append(cv2.GaussianBlur(g, (5, 5), 0).astype(np.float32)); ts.append(t)
    F = np.stack(frames); ts = np.array(ts)
    short = np.r_[0, np.abs(np.diff(F, axis=0)).mean(axis=(1, 2))]
    state = np.zeros(len(F))
    for i, t in enumerate(ts):
        ref = (ts >= t - 8) & (ts <= t - 4)
        if ref.sum() >= 3:
            state[i] = np.abs(F[i] - np.median(F[ref], axis=0)).mean()
    return ts, short, state


tot = []
for k, c in gt.items():
    t0 = time.time()
    ts, short, state = signals(c['path'])
    wall_time = time.time() - t0
    np.savez(os.path.join(OUT, k + '.npz'), ts=ts, short=short, state=state, wall_time_s=np.float32(wall_time))
    tot.append((wall_time, ts[-1]))
print(f'clips {len(tot)} | wall {sum(a for a, _ in tot):.1f}s for {sum(b for _, b in tot):.0f}s of video | '
      f'worst clip {max(a for a, _ in tot):.1f}s')
