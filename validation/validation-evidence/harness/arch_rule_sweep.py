"""CPU-only: re-run the questionnaire timeline rules on SAVED states with smoothing/persistence
and a per-rule keep-list chosen on dev only; report dev and lockbox aggregates. Prints no per-clip content."""
import collections, glob, itertools, json, os, sys
KIT, GTDIR = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(KIT, 'scripts'))
import timeline_rules as TR  # noqa: E402
gt = json.load(open(GTDIR + '/gt.json')); split = json.load(open(GTDIR + '/split.json'))
alias = {d: k for k, g in gt.items() for d in g['dups']}
S = {}
for p in glob.glob(os.path.join(KIT, 'runs/q35_9b_fp8/states/*.jsonl')):
    rows = [json.loads(l) for l in open(p, encoding='utf-8')]
    smp = sorted(({'t': r['t'], 'state': r['state']} for r in rows if r.get('ok') and isinstance(r.get('state'), dict)), key=lambda s: s['t'])
    vid = rows[0]['video']; S[alias.get(vid, vid)] = smp
ev = lambda ids: [(k, t) for k in ids if gt[k]['violation'] for t in gt[k]['org_times']]

def run(params, keep=None):
    out = {}
    for k, smp in S.items():
        V, _ = TR.detect(smp, params)
        out[k] = [v for v in V if keep is None or v['rule'] in keep]
    return out

def score(out, ids, tau=3):
    tp = sum(bool(out[k]) for k in ids if gt[k]['violation']); nv = sum(gt[k]['violation'] for k in ids)
    fp = sum(bool(out[k]) for k in ids if not gt[k]['violation']); nc = len(ids) - nv
    e = ev(ids)
    anyh = sum(any(abs(v['t'] - t) <= tau for v in out[k]) for k, t in e)
    top = sum(bool(out[k]) and abs(out[k][0]['t'] - t) <= tau for k, t in e)
    return f'recall {tp}/{nv} cleanFP {fp}/{nc} acc {tp + nc - fp}/{len(ids)} | ±{tau}s any {anyh}/{len(e)} first {top}/{len(e)} | ev/clip {sum(len(out[k]) for k in ids)/len(ids):.1f}'

dev = [k for k in gt if split[k] == 'dev']; lock = [k for k in gt if split[k] == 'lockbox']; allk = list(gt)
base = run({})
print('baseline (kit defaults) all :', score(base, allk))
# per-rule clip-level fire rates on DEV only
fire = collections.defaultdict(lambda: [0, 0])
for k in dev:
    for r in {v['rule'] for v in base[k]}:
        fire[r][0 if gt[k]['violation'] else 1] += 1
print('dev per-rule fires (violation clips of 12, clean clips of 12):', dict(sorted((r, tuple(c)) for r, c in fire.items())))
keep = {r for r, (a, b) in fire.items() if a > b}
print('keep-list chosen on dev (fires more on violation than clean):', sorted(keep))
best = None
grid = list(itertools.product([1, 2, 3], [2, 3, 4], [1.0, 1.5, 2.0]))
for sk, ms, sc in grid:
    prm = {'smooth_k': sk, 'min_samples': ms, **{x: TR.P[x] * sc for x in ('min_away_s', 'safe_open_s', 'door_open_s')}}
    o = run(prm, keep)
    d_tp = sum(bool(o[k]) for k in dev if gt[k]['violation']); d_fp = sum(bool(o[k]) for k in dev if not gt[k]['violation'])
    key = (d_tp - d_fp, d_tp)
    if best is None or key > best[0]:
        best = (key, prm)
print('best params on dev:', best[1])
for name, prm, kp in (('defaults+keep', {}, keep), ('tuned+keep', best[1], keep), ('tuned, all rules', best[1], None)):
    o = run(prm, kp)
    print(f'{name:16} dev    :', score(o, dev)); print(f'{name:16} LOCKBOX:', score(o, lock))

print('--- sampling-step sensitivity on saved 1 s states (kit default rules, all 40) ---')
for step in (2, 3, 4):
    orig = dict(S)
    for off in range(step):
        for k in orig:
            S[k] = [s for s in orig[k] if round(s['t']) % step == off]
        o = run({'min_samples': 1} if step >= 3 else {})
        print(f'step {step}s offset {off}:', score(o, allk))
    S.update(orig)
