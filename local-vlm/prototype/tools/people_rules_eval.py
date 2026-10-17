"""Проверка правил по людям из D-FINE на всех видео: где срабатывают и совпадают ли с метками.

  python prototype/tools/people_rules_eval.py --det prototype/work/runs/dfine --zoom prototype/work/runs/proto_4b/zoom \
      --states prototype/work/runs/proto_4b_v2/states [--crowd 3 --crowd_s 4 --stand 2 --stand_s 2]
"""
import argparse, csv, glob, json, os, sys
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from people_analyze import in_room   # noqa: E402

AR_FIX = 1 / 0.547         # кадры 464×848: перевод долей в пиксельное соотношение сторон


def per_second(rows, desk, door, W_over_H):
    T = int(rows[-1]['t']) + 1 if rows else 0
    n, s = [], []
    for sec in range(T):
        fr = [r for r in rows if sec <= r['t'] < sec + 1]
        ins = [[q for q in r['persons'] if in_room(q, desk, door)] for r in fr]
        n.append(round(median(len(x) for x in ins)) if ins else 0)
        s.append(round(median(sum((q[3] - q[1]) / max(1e-6, q[2] - q[0]) / W_over_H >= 2.1 for q in x) for x in ins)) if ins else 0)
    return n, s


def runs(xs, pred, min_len):
    out, i = [], 0
    while i < len(xs):
        if pred(xs[i]):
            j = i
            while j + 1 < len(xs) and pred(xs[j + 1]): j += 1
            if j - i + 1 >= min_len: out.append((i, j))
            i = j + 1
        else: i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--det', required=True); ap.add_argument('--zoom', required=True); ap.add_argument('--states', required=True)
    ap.add_argument('--crowd', type=int, default=3); ap.add_argument('--crowd_s', type=int, default=4)
    ap.add_argument('--stand', type=int, default=2); ap.add_argument('--stand_s', type=int, default=2)
    a = ap.parse_args()
    kit = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'brev_kit', 'data')
    gt = {}
    for r in csv.DictReader(open(os.path.join(kit, 'gt_violations.csv'), encoding='utf-8'), delimiter=';'):
        gt.setdefault(r['video'], []).append(f"{r['t']}:{r['expected_codex_ids'].split('|')[0]}")
    dup = {r['video'] for r in csv.DictReader(open(os.path.join(kit, 'videos.csv'), encoding='utf-8'), delimiter=';') if r['duplicate_of']}
    hits = {'two_clients': [], 'outsider': []}
    for p in sorted(glob.glob(os.path.join(a.det, 'X-*.jsonl')), key=lambda p: int(os.path.basename(p)[2:-6])):
        vid = os.path.basename(p)[:-6]
        if vid in dup: continue
        rows = [json.loads(l) for l in open(p, encoding='utf-8')]
        zp = os.path.join(a.zoom, vid + '.json'); boxes = json.load(open(zp, encoding='utf-8'))['boxes'] if os.path.exists(zp) else {}
        st = [json.loads(l) for l in open(os.path.join(a.states, vid + '.jsonl'), encoding='utf-8')] if os.path.exists(os.path.join(a.states, vid + '.jsonl')) else []
        coll = lambda sec: any(abs(x['t'] - sec) <= 1.5 and x['state']['collector_present'] for x in st)
        n, s = per_second(rows, boxes.get('desk'), boxes.get('door'), 1 / AR_FIX)
        ev = []
        for i, j in runs(n, lambda v: v >= a.crowd, a.crowd_s):
            if sum(coll(k) for k in range(i, j + 1)) <= (j - i + 1) / 2: ev.append(('two_clients', i))
        for i, j in runs(s, lambda v: v >= a.stand, a.stand_s): ev.append(('outsider', i))
        for r, t in ev: hits[r].append((vid, t))
        tag = 'чистое' if vid not in gt else ', '.join(gt[vid])
        if ev or vid in gt: print(f"{vid:5s} [{tag}]  ->  {', '.join(f'{r}@{t}' for r, t in ev) or '-'}")
    clean = lambda v: v not in gt
    for r, hs in hits.items():
        print(f"{r}: на нарушениях {sorted({v for v, _ in hs if not clean(v)})}, на чистых {sorted({v for v, _ in hs if clean(v)})}")


if __name__ == '__main__':
    main()
