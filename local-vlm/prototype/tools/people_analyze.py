"""Анализ рамок D-FINE: люди в комнате по времени против полей 4B и меток.

  python prototype/tools/people_analyze.py --det prototype/work/runs/dfine --zoom prototype/work/runs/proto_4b/zoom \
      --states prototype/work/runs/proto_4b_v2/states

Человек «в комнате», если его ноги (низ рамки) не выше линии пола у стола/двери: люди за стеклом стоят дальше и выше в кадре.
Стоит — рамка вытянута (высота/ширина ≥ STAND_AR), сидит — ниже.
Строка на видео: n — людей в комнате по секундам (0–9), s — из них стоят, 4b — сколько людей видела 4B (у кассира + клиенты).
"""
import argparse, csv, glob, json, os
from statistics import median

STAND_AR = 2.1


def in_room(p, desk, door):
    x1, y1, x2, y2 = p[:4]
    floor = min(desk[1] if desk else 1, (door[3] if door else 1)) / 1000 - 0.04
    return y2 >= floor or (y2 - y1) >= 0.30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--det', required=True); ap.add_argument('--zoom', required=True); ap.add_argument('--states', required=True)
    a = ap.parse_args()
    kit = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'brev_kit', 'data')
    gt = {}
    for r in csv.DictReader(open(os.path.join(kit, 'gt_violations.csv'), encoding='utf-8'), delimiter=';'):
        gt.setdefault(r['video'], []).append(f"{r['t']}:{r['type_ru'][:28]}")
    for p in sorted(glob.glob(os.path.join(a.det, 'X-*.jsonl')), key=lambda p: int(os.path.basename(p)[2:-6])):
        vid = os.path.basename(p)[:-6]
        rows = [json.loads(l) for l in open(p, encoding='utf-8')]
        zp = os.path.join(a.zoom, vid + '.json'); boxes = json.load(open(zp, encoding='utf-8'))['boxes'] if os.path.exists(zp) else {}
        desk, door = boxes.get('desk'), boxes.get('door')
        sp = os.path.join(a.states, vid + '.jsonl')
        st = [json.loads(l) for l in open(sp, encoding='utf-8')] if os.path.exists(sp) else []
        n_sec, s_sec, b_sec = [], [], []
        T = int(rows[-1]['t']) + 1 if rows else 0
        for sec in range(T):
            fr = [r for r in rows if sec <= r['t'] < sec + 1]
            ins = [[q for q in r['persons'] if in_room(q, desk, door)] for r in fr]
            n_sec.append(round(median(len(x) for x in ins)) if ins else 0)
            s_sec.append(round(median(sum((q[3] - q[1]) / max(1e-6, q[2] - q[0]) * (1 / 0.547) >= STAND_AR for q in x) for x in ins)) if ins else 0)
            near = [s for s in st if abs(s['t'] - sec) <= 0.75]
            b_sec.append(near[0]['state']['people_cashier_side'] + near[0]['state']['clients_at_desk'] if near else -1)
        line = lambda xs: ''.join('·' if x == 0 else ('?' if x < 0 else str(min(9, x))) for x in xs)
        print(f"{vid:5s} {'; '.join(gt.get(vid, ['чистое']))}")
        print(f"   n   {line(n_sec)}\n   s   {line(s_sec)}\n   4b  {line(b_sec)}")


if __name__ == '__main__':
    main()
