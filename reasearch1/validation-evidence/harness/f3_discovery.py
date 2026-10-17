"""F3: whole-video event discovery with a local VLM. No label times are used to choose inputs.

Configs (pre-registered):
  whole_1fps_s288 : entire clip in one prompt, 1 fps, short side 288 px
  whole_2fps_s288 : entire clip, 2 fps, short side 288 px
  chunk30_2fps_s288: consecutive 30 s chunks (2 s overlap), 2 fps, short side 288 px; times offset back to clip time
  (replaces the pre-registered chunk30_2fps_s448 after profiling: ~11k tokens/chunk hits the 12 GB memory-bound regime)
Verdict rule (pre-registered): primary = any parsed event; '_hm' variant = any event with confidence high/medium.
Writes preds/F3_<cfg>.json and preds/F3_<cfg>_hm.json, raw text to vlm_raw/F3_<cfg>.jsonl (private).
Usage: python -I f3_discovery.py <repo_root> <cfg> [all|dev|lockbox] [limit]
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompts, vlm  # noqa: E402

ROOT, CFG = sys.argv[1], sys.argv[2]
WHICH = sys.argv[3] if len(sys.argv) > 3 else 'all'
LIMIT = int(sys.argv[4]) if len(sys.argv) > 4 else None
P = os.path.join(ROOT, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
split = json.load(open(os.path.join(P, 'split.json')))
CFGS = {'whole_1fps_s288': (None, 1.0, 288), 'whole_2fps_s288': (None, 2.0, 288),
        'chunk30_2fps_s288': (30.0, 2.0, 288)}
chunk, fps, side = CFGS[CFG]

import av  # noqa: E402
def duration(path):
    with av.open(path) as c:
        s = c.streams.video[0]
        return float(s.duration * s.time_base) if s.duration else c.duration / 1e6

clips = [k for k in gt if WHICH == 'all' or split[k] == WHICH][:LIMIT]
os.makedirs(os.path.join(P, 'vlm_raw'), exist_ok=True); os.makedirs(os.path.join(P, 'preds'), exist_ok=True)
log = os.path.join(P, 'vlm_raw', f'F3_{CFG}.jsonl')
open(log, 'w').close()
model, proc, load_s = vlm.load()
print(f'model load {load_s:.1f}s', flush=True)

pred, pred_hm, parse_fail = {}, {}, 0
for k in clips:
    d = duration(gt[k]['path'])
    if chunk:
        jobs, s = [], 0.0
        while s < d - 1:
            jobs.append({'clip': k, 'path': gt[k]['path'], 't0': s, 't1': min(d, s + chunk), 'fps': fps, 'short_side': side})
            s += chunk - 2
    else:
        jobs = [{'clip': k, 'path': gt[k]['path'], 't0': 0.0, 't1': None, 'fps': fps, 'short_side': side}]
    t0 = time.time()
    res = vlm.run_jobs(model, proc, jobs, lambda j: prompts.DISCOVERY_V1, log=log)
    evs, err = [], None
    for r in res:
        if r['error']:
            err = r['error']; continue
        e, ok = vlm.parse_events(r['text'])
        parse_fail += not ok
        for x in e:
            t = vlm.to_sec(x.get('time_sec'))
            if t is not None:
                evs.append({'t': t + r['t0'], 'code': x.get('code'), 'conf': x.get('confidence')})
    rank = {'high': 0, 'medium': 1, 'low': 2}
    evs.sort(key=lambda e: rank.get(str(e['conf']).lower(), 3))
    rt = time.time() - t0
    pred[k] = {'verdict': 'violation' if evs else 'no_violation', 'events': evs, 'runtime_s': rt, 'error': err}
    hm = [e for e in evs if str(e['conf']).lower() in ('high', 'medium')]
    pred_hm[k] = {'verdict': 'violation' if hm else 'no_violation', 'events': hm, 'runtime_s': rt, 'error': err}
    print(f'{len(pred)}/{len(clips)} done | dur {d:.0f}s runtime {rt:.1f}s | peak {max((r.get("peak_gb", 0) for r in res), default=0):.1f} GB'
          f' | tokens {max((r.get("in_tokens", 0) for r in res), default=0)} | err {bool(err)}', flush=True)

suffix = '' if WHICH == 'all' and LIMIT is None else f'_{WHICH}{LIMIT or ""}'
json.dump(pred, open(os.path.join(P, 'preds', f'F3_{CFG}{suffix}.json'), 'w'))
json.dump(pred_hm, open(os.path.join(P, 'preds', f'F3_{CFG}{suffix}_hm.json'), 'w'))
print(f'parse failures {parse_fail} | wrote F3_{CFG}{suffix}')
