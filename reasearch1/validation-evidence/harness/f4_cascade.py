"""F4: proposer windows -> VLM verifier (VERIFY_V1) -> verdict.

Proposal contract (written by any proposer): validation-private/proposals/<name>.json
  {"_meta": {"runtime_s": {clip: s}}, clip: [{"t": centre_sec, "score": float}, ...]}  ranked best-first
Pre-registered: top-K=5 windows of 8 s, 4 fps, short side 448; verdict = any 'yes';
event time = model time_sec (+window start) if inside the window else window centre; order = proposer rank.
Writes preds/F4_<proposals>_K<k>.json. Usage: python -I f4_cascade.py <repo_root> <proposals> [K]
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompts, vlm  # noqa: E402

ROOT, NAME = sys.argv[1], sys.argv[2]
K = int(sys.argv[3]) if len(sys.argv) > 3 else 5
P = os.path.join(ROOT, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
props = json.load(open(os.path.join(P, 'proposals', NAME + '.json')))
prop_rt = props.get('_meta', {}).get('runtime_s', {})
model, proc, load_s = vlm.load()
log = os.path.join(P, 'vlm_raw', f'F4_{NAME}_K{K}.jsonl'); open(log, 'w').close()

pred = {}
for k in gt:
    t0 = time.time()
    jobs = [{'clip': k, 'path': gt[k]['path'], 't0': max(0.0, c['t'] - 4), 't1': c['t'] + 4, 'fps': 4.0,
             'short_side': 448, 'rank': i} for i, c in enumerate(props.get(k, [])[:K])]
    res = vlm.run_jobs(model, proc, jobs, lambda j: prompts.VERIFY_V1, log=log)
    evs, err = [], None
    for r in res:
        if r['error']:
            err = r['error']; continue
        m = re.search(r'\{.*\}', r['text'] or '', re.S)
        try:
            a = json.loads(m.group(0)) if m else {}
        except Exception:
            a = {}
        if str(a.get('violation', '')).lower().startswith('y'):
            t = vlm.to_sec(a.get('time_sec'))
            t = t + r['t0'] if t is not None and 0 <= t <= 8 else r['t0'] + 4
            evs.append({'t': t, 'code': a.get('code'), 'conf': None})
    rt = time.time() - t0 + float(prop_rt.get(k, 0.0))
    pred[k] = {'verdict': 'violation' if evs else 'no_violation', 'events': evs, 'runtime_s': rt, 'error': err}
    print(f'{len(pred)}/{len(gt)} windows {len(jobs)} runtime {rt:.1f}s err {bool(err)}', flush=True)
json.dump(pred, open(os.path.join(P, 'preds', f'F4_{NAME}_K{K}.json'), 'w'))
print('wrote', f'F4_{NAME}_K{K}')
