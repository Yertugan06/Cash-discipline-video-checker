"""F1: COCO detector (RT-DETR v2 r18, Apache-2.0) + zone-free temporal rules. Pre-registered; no fitted constants.

Step 1 (detect): 2 fps by PTS, full frame, cached to data/validation-private/f1_dets/<clip>.npz
Step 2 (rules), event time = rule onset; verdict = any rule fires:
  R-bag   231-12-1 : handbag/backpack (score>=0.5) in >=50% of frames of some 5 s window
  R-phone 231-12-2 : cell phone (score>=0.5) in >=3 frames within 3 s
  R-leave 231-22   : person count drops >=1 below the median of the preceding 5 s and stays lower for >=3 s
  R-laptop 48-71-9 : laptop/tv detected and no person centre within 1 box-width of it for >=3 s
Usage: python -I f1_rules.py <repo_root> [detect|rules|both] [cpu|cuda]
"""
import collections, json, os, sys, time

import av
import numpy as np

ROOT = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else 'both'
DEV = sys.argv[3] if len(sys.argv) > 3 else 'cuda'
P = os.path.join(ROOT, 'data', 'validation-private')
D = os.path.join(P, 'f1_dets'); os.makedirs(D, exist_ok=True)
gt = json.load(open(os.path.join(P, 'gt.json')))
FPS = 2.0
CLASSES = ('person', 'handbag', 'backpack', 'cell phone', 'laptop', 'tv')


def detect():
    import torch
    torch.set_num_threads(4)
    from transformers import AutoImageProcessor, AutoModelForObjectDetection
    name, rev = 'PekingU/rtdetr_v2_r18vd', '5650961749'
    proc = AutoImageProcessor.from_pretrained(name, revision=rev)
    model = AutoModelForObjectDetection.from_pretrained(name, revision=rev).to(DEV).eval()
    alias = {'tvmonitor': 'tv', 'tv monitor': 'tv', 'cellphone': 'cell phone', 'mobile phone': 'cell phone'}
    want = {i: alias.get(n, n) for i, n in model.config.id2label.items() if alias.get(n, n) in CLASSES}
    assert set(want.values()) == set(CLASSES), f'missing classes: {set(CLASSES) - set(want.values())}'
    times = []
    for k, c in gt.items():
        t0 = time.time(); rows = []
        with av.open(c['path']) as cont:
            s = cont.streams.video[0]; s.thread_type = 'AUTO'; nxt = 0.0
            for f in cont.decode(s):
                t = float(f.pts * s.time_base)
                if t + 1e-6 < nxt:
                    continue
                nxt = t + 1 / FPS
                img = f.to_image()
                with torch.inference_mode():
                    out = model(**proc(images=img, return_tensors='pt').to(DEV))
                r = proc.post_process_object_detection(out, threshold=0.3, target_sizes=[img.size[::-1]])[0]
                for sc, lb, bx in zip(r['scores'].tolist(), r['labels'].tolist(), r['boxes'].tolist()):
                    if lb in want:
                        rows.append([t, CLASSES.index(want[lb]), sc, *bx])
                rows.append([t, -1, 0, 0, 0, 0, 0])  # frame marker so empty frames keep their timestamp
        np.save(os.path.join(D, k + '.npy'), np.array(rows, dtype=np.float32))
        times.append((k, time.time() - t0))
    json.dump(dict(times), open(os.path.join(D, '_runtime.json'), 'w'))
    print(f'detect: {len(times)} clips, total {sum(t for _, t in times):.0f}s, worst {max(t for _, t in times):.1f}s on {DEV}')


def rules(k):
    a = np.load(os.path.join(D, k + '.npy'))
    ts = np.unique(a[a[:, 1] == -1, 0])
    per = {t: a[(a[:, 0] == t) & (a[:, 1] >= 0) & (a[:, 2] >= 0.5)] for t in ts}
    has = lambda t, *cls: any(int(r[1]) in [CLASSES.index(c) for c in cls] for r in per[t])
    ev = []
    for t in ts:  # R-bag
        w = [u for u in ts if t <= u < t + 5]
        if len(w) >= 6 and sum(has(u, 'handbag', 'backpack') for u in w) >= 0.5 * len(w):
            ev.append({'t': float(t), 'code': '231-12-1', 'conf': None}); break
    for t in ts:  # R-phone
        w = [u for u in ts if t <= u < t + 3]
        if sum(has(u, 'cell phone') for u in w) >= 3:
            ev.append({'t': float(t), 'code': '231-12-2', 'conf': None}); break
    cnt = {t: int(sum(int(r[1]) == 0 for r in per[t])) for t in ts}
    for t in ts:  # R-leave
        prev = [cnt[u] for u in ts if t - 5 <= u < t]
        nxt = [cnt[u] for u in ts if t <= u < t + 3]
        if len(prev) >= 6 and len(nxt) >= 5 and all(c <= np.median(prev) - 1 for c in nxt):
            ev.append({'t': float(t), 'code': '231-22', 'conf': None}); break

    def unattended(u):
        for r in per[u]:
            if int(r[1]) in (CLASSES.index('laptop'), CLASSES.index('tv')):
                cx, cy, w = (r[3] + r[5]) / 2, (r[4] + r[6]) / 2, r[5] - r[3]
                if not any(int(p[1]) == 0 and np.hypot((p[3] + p[5]) / 2 - cx, (p[4] + p[6]) / 2 - cy) <= w for p in per[u]):
                    return True
        return False
    for t in ts:  # R-laptop
        w = [u for u in ts if t <= u < t + 3]
        if len(w) >= 5 and all(unattended(u) for u in w):
            ev.append({'t': float(t), 'code': '48-71-9', 'conf': None}); break
    return ev


if MODE in ('detect', 'both'):
    detect()
if MODE in ('rules', 'both'):
    rt = json.load(open(os.path.join(D, '_runtime.json')))
    pred, fires = {}, collections.Counter()
    for k in gt:
        ev = rules(k)
        for e in ev:
            fires[(e['code'], 'viol' if gt[k]['violation'] else 'clean')] += 1
        pred[k] = {'verdict': 'violation' if ev else 'no_violation', 'events': ev, 'runtime_s': rt[k], 'error': None}
    json.dump(pred, open(os.path.join(P, 'preds', 'F1_coco_rules.json'), 'w'))
    print('rule fires (clips):', {f'{c}/{s}': n for (c, s), n in sorted(fires.items())})
