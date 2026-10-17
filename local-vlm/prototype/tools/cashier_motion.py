"""Активность кассира в момент ухода клиента: движение пикселей в рамке кассира (детектор), без нейросети.
Кассир — человек в комнате, ближе всех к камере (низ рамки ниже всех). Движение = средняя |разница| соседних кадров
(5 кадров/с, градации серого) в верхних 2/3 рамки кассира (руки, стол), окно [t−1, t+3].

  python prototype/tools/cashier_motion.py --videos open/open/videos --det prototype/work/runs/dfine \
      --zoom prototype/work/runs/proto_4b/zoom --cand prototype/work/runs/leave_candidates.json
"""
import argparse, glob, json, os, subprocess, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import people   # noqa: E402


def motion(video, t, box, fps=5):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-ss', f'{max(0, t - 1):.2f}', '-t', '4', '-i', video, '-vf', f'fps={fps}',
                        os.path.join(tmp, '%03d.png')])
        fr = sorted(glob.glob(os.path.join(tmp, '*.png')))
        prev, vals = None, []
        for p in fr:
            im = Image.open(p).convert('L'); W, H = im.size
            x1, y1, x2, y2 = box; y2 = y1 + (y2 - y1) * 2 / 3
            a = np.asarray(im.crop((int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H))), dtype=np.float32)
            if prev is not None and prev.shape == a.shape: vals.append(float(np.abs(a - prev).mean()))
            prev = a
    return round(float(np.mean(vals)), 2) if vals else None, round(float(np.percentile(vals, 90)), 2) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', required=True); ap.add_argument('--det', required=True); ap.add_argument('--zoom', required=True); ap.add_argument('--cand', required=True)
    a = ap.parse_args()
    files = {os.path.splitext(os.path.basename(f))[0].replace('Х', 'X'): f for f in glob.glob(os.path.join(a.videos, '*'))}
    for c in json.load(open(a.cand)):
        vid, t = c['video'], c['t']
        rows = {r['t']: r['persons'] for r in map(json.loads, open(os.path.join(a.det, vid + '.jsonl')))}
        boxes = json.load(open(os.path.join(a.zoom, vid + '.json'), encoding='utf-8'))['boxes']
        near = [ps for tt, ps in rows.items() if t <= tt <= t + 1]
        cands = [p for ps in near for p in ps if people.in_room(p, boxes)]
        if not cands: print(vid, t, 'no cashier box'); continue
        cashier = max(cands, key=lambda p: p[3])          # ближе всех к камере
        m, p90 = motion(files[vid], t, cashier[:4])
        print(f"{vid:5s} {t:5.1f}  motion mean {m}  p90 {p90}  {'<- X-34 нарушение' if vid == 'X-34' else ''}")


if __name__ == '__main__':
    main()
