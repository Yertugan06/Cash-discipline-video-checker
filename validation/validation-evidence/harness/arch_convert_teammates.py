"""Convert teammate runs to the harness prediction format (private, job tmp only)."""
import glob, json, re, sys
R = sys.argv[1]; OUT = sys.argv[2]
gt = json.load(open(OUT + '/gt.json'))
alias = {}
for k, g in gt.items():
    alias[k] = k
    for d in g['dups']:
        alias[d] = k

# Qwen3.5-9B questionnaire (forte_brev_kit)
for run in ('q35_9b_fp8',):
    base = f'{R}/forte_brev_kit/brev_kit/runs/{run}'
    meta = json.load(open(base + '/run_meta.json'))['videos']
    pred = {}
    for f in glob.glob(base + '/violations/*.json'):
        d = json.load(open(f)); k = alias.get(d['video'], d['video'])
        ev = []
        for v in d['violations']:
            ids = v.get('codex_ids') or []
            ev.append({'t': v['timecode_sec'], 'code': ids[0] if ids else None, 'codes': ids, 'conf': None})
        pred[k] = {'verdict': d['verdict'], 'events': ev, 'runtime_s': meta.get(d['video'], {}).get('wall_s'), 'error': None}
    json.dump(pred, open(f'{OUT}/preds/{run}.json', 'w'))
    print(run, len(pred), 'sample codes', sorted({e['code'] for p in pred.values() for e in p['events']})[:12])

# forte-cash-checker F1 app, full 5 fps GPU run
r = json.load(open(f'{R}/forte-model-check-20261017-1114/eval_runtime/reports/gpu/results.json'))
pred = {}
for e in r:
    k = next(alias[a] for a in e['aliases'] if a in alias)
    res = e['result']
    vs = sorted(res.get('violations', []), key=lambda v: -(v.get('confidence') or 0))
    ev = [{'t': v['timecode_sec'], 'code': re.sub(r'^NBRK\s*', '', v.get('source') or ''), 'conf': v.get('confidence')} for v in vs]
    pred[k] = {'verdict': res['verdict'], 'events': ev, 'runtime_s': e['end_to_end_sec'], 'error': e['error']}
json.dump(pred, open(f'{OUT}/preds/f1_app_gpu5fps.json', 'w'))
print('f1_app', len(pred), 'sample codes', sorted({x['code'] for p in pred.values() for x in p['events']})[:12])
