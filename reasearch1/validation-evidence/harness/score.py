"""Common scorer. Reads a private prediction file and prints AGGREGATES only.

Prediction file (validation-private/preds/<name>.json):
  {clip_id: {"verdict": "violation"|"no_violation", "events": [{"t": sec, "code": str|None, "conf": float|None}],
             "runtime_s": float, "error": str|None}}
Events are ordered by the system's own priority; events[0] is the "top-1" event.

Usage: python -I score.py <repo_root> <pred_name> [--split dev|lockbox|all]
"""
import collections, json, math, os, statistics as st, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_utils import code_match  # noqa: E402

ROOT, NAME = sys.argv[1], sys.argv[2]
SPLIT = sys.argv[sys.argv.index('--split') + 1] if '--split' in sys.argv else 'all'
P = os.path.join(ROOT, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
split = json.load(open(os.path.join(P, 'split.json')))
pred = json.load(open(os.path.join(P, 'preds', NAME + '.json')))
ids = [k for k in gt if SPLIT == 'all' or split[k] == SPLIT]
missing = [k for k in ids if k not in pred]
ids = [k for k in ids if k in pred]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 2), round((c + h) / d, 2))


print(f'== {NAME} | split={SPLIT} | n={len(ids)} | missing={len(missing)} | errors={sum(1 for k in ids if pred[k].get("error"))}')
conf = collections.Counter()
by_layout = collections.defaultdict(collections.Counter)
for k in ids:
    p = pred[k]['verdict'] == 'violation'; y = gt[k]['violation']
    cell = 'TP' if p and y else 'FN' if y else 'FP' if p else 'TN'
    conf[cell] += 1; by_layout[gt[k]['layout']][cell] += 1
tp, fn, fp, tn = conf['TP'], conf['FN'], conf['FP'], conf['TN']
print(f'video  TP={tp} FN={fn} FP={fp} TN={tn} | recall {tp}/{tp + fn} {wilson(tp, tp + fn)} | '
      f'clean-FP {fp}/{fp + tn} {wilson(fp, fp + tn)} | acc {(tp + tn)}/{len(ids)}')
for lay, c in sorted(by_layout.items()):
    print(f'   layout {lay!r:22}: ' + ' '.join(f'{x}={c[x]}' for x in ('TP', 'FN', 'FP', 'TN')))

ev = [(k, t) for k in ids if gt[k]['violation'] for t in gt[k]['org_times']]
n_ev = len(ev)
for conv, off in (('N.0', 0.0), ('N+0.5', 0.5)):
    row_any, row_top = [], []
    for tau in (1, 2, 3, 5):
        a = sum(1 for k, t in ev if any(abs(e['t'] - (t + off)) <= tau for e in pred[k]['events']))
        b = sum(1 for k, t in ev if pred[k]['events'] and abs(pred[k]['events'][0]['t'] - (t + off)) <= tau)
        row_any.append(f'±{tau}s {a}/{n_ev}'); row_top.append(f'±{tau}s {b}/{n_ev}')
    print(f'loc[{conv}] any-event: ' + ' '.join(row_any) + ' | top-1: ' + ' '.join(row_top))
errs = [min(abs(e['t'] - t) for e in pred[k]['events']) for k, t in ev if pred[k]['events']]
if errs:
    print(f'   |nearest error| median {st.median(errs):.1f}s, events with any prediction {len(errs)}/{n_ev}')

nv = [len(pred[k]['events']) for k in ids if gt[k]['violation']]
nc = [len(pred[k]['events']) for k in ids if not gt[k]['violation']]
print(f'events/violation clip mean {st.mean(nv) if nv else 0:.2f} | events/clean clip mean {st.mean(nc) if nc else 0:.2f}')

rel = [k for k in ids if gt[k]['violation'] and gt[k]['human_reliable']]
hit_code = sum(1 for k in rel if any(code_match(e.get('code'), gt[k]['human'][0]['norm1'])
                                     for e in pred[k]['events']))
hit_code_loc = sum(1 for k in rel if any(code_match(e.get('code'), gt[k]['human'][0]['norm1'])
                                         and min(abs(e['t'] - t) for t in gt[k]['org_times']) <= 3
                                         for e in pred[k]['events']))
print(f'mechanism (reliable subset n={len(rel)}): human norm-1 code among predicted codes {hit_code}/{len(rel)}, '
      f'and within ±3s {hit_code_loc}/{len(rel)}')
rt = [pred[k]['runtime_s'] for k in ids if pred[k].get('runtime_s') is not None]
if rt:
    print(f'runtime s: median {st.median(rt):.1f} max {max(rt):.1f} total {sum(rt):.0f}')
