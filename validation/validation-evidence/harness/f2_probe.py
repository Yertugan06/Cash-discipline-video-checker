"""Addendum B1: frozen image encoder + linear probe, leave-one-group-out (aggregates only).

Features: 2 fps by PTS, top and bottom square crops of the portrait frame, encoder pooled output, concatenated.
Window feature at t = mean of (per-clip mean-centred) frame features in [t-2, t+2].
Train: label windows (+) vs clean-clip windows every 2 s and violation windows >= 6 s from labels (-).
Writes preds/F2_<enc>[_raw].json for score.py. Usage: python -I f2_probe.py <repo_root> <dinov2|siglip2> [raw]
"""
import json, os, sys, time

import av
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT, ENC = sys.argv[1], sys.argv[2]
RAW = len(sys.argv) > 3 and sys.argv[3] == 'raw'  # shortcut control: no per-clip centring
P = os.path.join(ROOT, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
MODELS = {'dinov2': ('facebook/dinov2-base', 'f9e44c814b77203eaa57a6bdbbd535f21ede1415'),
          'siglip2': ('google/siglip2-base-patch16-384', 'f775b65a79762255128c981547af89addcfe0f88')}
C = os.path.join(P, f'f2_feats_{ENC}'); os.makedirs(C, exist_ok=True)


def extract():
    from transformers import AutoImageProcessor, AutoModel
    name, rev = MODELS[ENC]
    proc = AutoImageProcessor.from_pretrained(name, revision=rev)
    model = AutoModel.from_pretrained(name, revision=rev).to('cuda').eval()
    enc = model.vision_model if ENC == 'siglip2' else model
    rt = {}
    for k, c in gt.items():
        out = os.path.join(C, k + '.npz')
        if os.path.exists(out):
            continue
        t0 = time.time(); ts, imgs = [], []
        with av.open(c['path']) as cont:
            s = cont.streams.video[0]; s.thread_type = 'AUTO'; nxt = 0.0
            for f in cont.decode(s):
                t = float(f.pts * s.time_base)
                if t + 1e-6 < nxt:
                    continue
                nxt = t + 0.5
                im = f.to_image(); w, h = im.size; q = min(w, h)
                imgs += [im.crop((0, 0, q, q)), im.crop((0, h - q, q, h))]; ts.append(t)
        feats = []
        with torch.inference_mode():
            for i in range(0, len(imgs), 64):
                x = proc(images=imgs[i:i + 64], return_tensors='pt').to('cuda')
                o = enc(pixel_values=x['pixel_values'])
                feats.append(o.pooler_output.float().cpu().numpy())
        F = np.concatenate(feats).reshape(len(ts), -1)
        np.savez(out, ts=np.array(ts), F=F)
        rt[k] = time.time() - t0
    if rt:
        json.dump(rt, open(os.path.join(C, '_runtime.json'), 'w'))


def windows(k, step):
    d = np.load(os.path.join(C, k + '.npz')); ts, F = d['ts'], d['F']
    if not RAW:
        F = F - F.mean(0)
    cs = np.arange(0, ts[-1] + 1e-6, step)
    W = np.stack([F[(ts >= c - 2) & (ts <= c + 2)].mean(0) if ((ts >= c - 2) & (ts <= c + 2)).any() else F[np.abs(ts - c).argmin()] for c in cs])
    return cs, W


extract()
dense = {k: windows(k, 0.5) for k in gt}


def train_set(keys):
    X, y = [], []
    for k in keys:
        cs, W = dense[k]
        lab = [t + 0.5 for t in gt[k]['org_times']]
        for i, c in enumerate(cs):
            if lab and min(abs(c - t) for t in lab) <= 0.25:
                X.append(W[i]); y.append(1)
            elif (not lab and i % 4 == 0) or (lab and i % 4 == 0 and min(abs(c - t) for t in lab) >= 6):
                X.append(W[i]); y.append(0)
    return np.array(X), np.array(y)


groups = sorted({c['group'] for c in gt.values()})
oof = {}
for g in groups:
    tr = [k for k in gt if gt[k]['group'] != g]
    X, y = train_set(tr)
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight='balanced', max_iter=3000)).fit(X, y)
    for k in gt:
        if gt[k]['group'] == g:
            oof[k] = clf.predict_proba(dense[k][1])[:, 1]

# window AUC: label windows vs same-time windows in the matched clean twin, and vs all clean windows
pos, twin = [], []
for k, c in gt.items():
    if not c['violation']:
        continue
    cs = dense[k][0]
    for t in c['org_times']:
        pos.append(oof[k][np.abs(cs - (t + 0.5)).argmin()])
        for m in gt:
            if gt[m]['group'] == c['group'] and not gt[m]['violation']:
                twin.append(oof[m][np.abs(dense[m][0] - (t + 0.5)).argmin()])
clean_all = np.concatenate([oof[k] for k in gt if not gt[k]['violation']])
auc = lambda a, b: roc_auc_score([1] * len(a) + [0] * len(b), list(a) + list(b))
mx = {k: float(oof[k].max()) for k in gt}
yv = [gt[k]['violation'] for k in gt]
dur = {k: float(dense[k][0][-1]) for k in gt}
print(f'== F2 {ENC}{" RAW (no centring)" if RAW else ""} | LOGO over {len(groups)} groups')
print(f'window AUC: label vs matched twin {auc(pos, twin):.2f} (n={len(pos)}/{len(twin)}) | label vs all clean windows {auc(pos, clean_all):.2f}')
print(f'video AUC (max window score) {roc_auc_score(yv, [mx[k] for k in gt]):.2f} | shortcut ref: duration AUC {roc_auc_score(yv, [-dur[k] for k in gt]):.2f}')

# cross-fitted threshold: for each held-out group, balanced-accuracy-optimal threshold on the other groups' max scores
pred = {}
rt = json.load(open(os.path.join(C, '_runtime.json'))) if os.path.exists(os.path.join(C, '_runtime.json')) else {}
for k in gt:
    others = [j for j in gt if gt[j]['group'] != gt[k]['group']]
    def bacc(th):
        tp = sum(mx[j] >= th and gt[j]['violation'] for j in others); p = sum(gt[j]['violation'] for j in others)
        tn = sum(mx[j] < th and not gt[j]['violation'] for j in others)
        return tp / p + tn / (len(others) - p)
    th = max((mx[j] for j in others), key=bacc)
    cs = dense[k][0]
    v = mx[k] >= th
    pred[k] = {'verdict': 'violation' if v else 'no_violation',
               'events': [{'t': float(cs[oof[k].argmax()]), 'code': None, 'conf': mx[k]}] if v else [],
               'runtime_s': rt.get(k), 'error': None}
# localization independent of verdict: top window of every violation clip
loc = {tau: sum(1 for k, c in gt.items() if c['violation'] for t in c['org_times']
                if abs(dense[k][0][oof[k].argmax()] - t) <= tau) for tau in (1, 2, 3, 5)}
print('top-1 localization (argmax window, all violation clips):', ' '.join(f'±{t}s {n}/22' for t, n in loc.items()))
name = f'F2_{ENC}{"_raw" if RAW else ""}'
json.dump(pred, open(os.path.join(P, 'preds', name + '.json'), 'w'))
print('wrote', name)
