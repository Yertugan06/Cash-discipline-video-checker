"""Точность анкеты по золотым кадрам: по каждому полю, со списком ошибок.

python scripts/eval_states.py --pred runs/q35_9b/states --gold data/gold_states.csv --out runs/q35_9b/report_states.md
"""
import argparse, csv, glob, json, os
from collections import defaultdict


def norm(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    return str(v).strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pred', required=True, help='папка states/ из run_vlm.py')
    ap.add_argument('--gold', required=True)
    ap.add_argument('--tol', type=float, default=0.3, help='допуск по времени при поиске кадра, с')
    ap.add_argument('--out')
    a = ap.parse_args()
    pred = defaultdict(list)
    for p in glob.glob(os.path.join(a.pred, '*.jsonl')):
        for ln in open(p, encoding='utf-8'):
            r = json.loads(ln); pred[r['video']].append(r)
    gold = list(csv.DictReader(open(a.gold, encoding='utf-8'), delimiter=';'))
    per = defaultdict(lambda: [0, 0]); errors = []; missing = 0
    for g in gold:
        cands = [r for r in pred.get(g['video'], []) if abs(r['t'] - float(g['t'])) <= a.tol]
        if not cands:
            missing += 1; continue
        r = min(cands, key=lambda r: abs(r['t'] - float(g['t'])))
        got = norm((r.get('state') or {}).get(g['field'], 'NO_ANSWER'))
        per[g['field']][1] += 1
        if got == norm(g['value']): per[g['field']][0] += 1
        else: errors.append((g['video'], g['t'], g['field'], g['value'], got, g.get('note', '')))
    tot_ok = sum(v[0] for v in per.values()); tot = sum(v[1] for v in per.values())
    lines = [f'# Анкета на золотых кадрах', f'Всего проверок: {tot}, верно: {tot_ok} ({tot_ok / max(1, tot):.0%}); не найдено кадров: {missing}', '',
             '| Поле | Верно | Всего | Точность |', '|---|---|---|---|']
    for f, (ok, n) in sorted(per.items(), key=lambda x: x[1][0] / max(1, x[1][1])):
        lines.append(f'| {f} | {ok} | {n} | {ok / max(1, n):.0%} |')
    lines += ['', '## Ошибки', '| Видео | t | Поле | Ожидалось | Модель | Комментарий |', '|---|---|---|---|---|---|']
    lines += [f'| {e[0]} | {e[1]} | {e[2]} | {e[3]} | {e[4]} | {e[5]} |' for e in errors]
    txt = '\n'.join(lines); print(txt)
    if a.out: open(a.out, 'w', encoding='utf-8').write(txt)


if __name__ == '__main__':
    main()
