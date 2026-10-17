"""Verification probe (HX4): the VLM sees a short window and answers the frozen VERIFY_V1 checklist.

Window sets (8 s, 4 fps, short side 448), all built before inference, seed 26:
  pos      : organizer label second +- 4 s, every organizer event
  pair_neg : same absolute time in the paired clean clip of the same group (matched hard negative)
  rand_neg : one random 8 s window per clean clip
  off_neg  : one window inside each violation clip whose centre is >= 10 s from every label (if the clip allows)
Prints yes-rates per set, code agreement on the mechanism-reliable subset, time error; raw text stays private.
Usage: python -I verify_windows.py <repo_root> [fps] [short_side] [tag] [v1|items] [all|dev|lockbox]
"""
import collections, json, os, random, statistics as st, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompts, vlm  # noqa: E402

ROOT = sys.argv[1]
FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
SIDE = int(sys.argv[3]) if len(sys.argv) > 3 else 448
TAG = sys.argv[4] if len(sys.argv) > 4 else f'{int(FPS)}fps_s{SIDE}'
PROMPT = sys.argv[5] if len(sys.argv) > 5 else 'v1'
WHICH = sys.argv[6] if len(sys.argv) > 6 else 'all'
split = json.load(open(os.path.join(ROOT, 'validation-private', 'split.json')))
P = os.path.join(ROOT, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
import av  # noqa: E402


def duration(path):
    with av.open(path) as c:
        s = c.streams.video[0]
        return float(s.duration * s.time_base) if s.duration else c.duration / 1e6


gt = {k: c for k, c in gt.items() if WHICH == 'all' or split[k] == WHICH}
dur = {k: duration(c['path']) for k, c in gt.items()}
rng = random.Random(26)
win = lambda k, c: (max(0.0, min(c - 4, dur[k] - 8)), min(dur[k], max(c - 4, 0) + 8))
jobs = []
for k, c in gt.items():
    if c['violation']:
        for t in c['org_times']:
            jobs.append(('pos', k, *win(k, t + 0.5), t))
            for m in gt:
                if gt[m]['group'] == c['group'] and not gt[m]['violation']:
                    jobs.append(('pair_neg', m, *win(m, t + 0.5), None))
        far = [x for x in range(4, int(dur[k]) - 4) if all(abs(x - t) >= 10 for t in c['org_times'])]
        if far:
            jobs.append(('off_neg', k, *win(k, rng.choice(far)), None))
    else:
        jobs.append(('rand_neg', k, *win(k, rng.uniform(4, dur[k] - 4)), None))
print('windows per set:', dict(collections.Counter(j[0] for j in jobs)), flush=True)

model, proc, load_s = vlm.load()
log = os.path.join(P, 'vlm_raw', f'verify_{TAG}.jsonl'); os.makedirs(os.path.dirname(log), exist_ok=True)
open(log, 'w').close()
res = vlm.run_jobs(model, proc, [{'clip': k, 'path': gt[k]['path'], 't0': a, 't1': b, 'fps': FPS, 'short_side': SIDE,
                                  'set': s, 'label_t': lt} for s, k, a, b, lt in jobs],
                   lambda j: prompts.VERIFY_V1 if PROMPT == 'v1' else prompts.VERIFY_ITEMS_V2, log=log)


def answer(r):
    if r['error'] or not r['text']:
        return None
    import re
    m = re.search(r'\{.*\}', r['text'], re.S)
    try:
        a = json.loads(m.group(0)) if m else None
    except Exception:
        return None
    if a is not None and PROMPT == 'items':
        a['violation'], a['code'] = prompts.parse_items(a)
    return a


yes = collections.defaultdict(list); code_ok, terr, parse_fail = [], [], 0
import score_utils  # noqa: E402
for r in res:
    a = answer(r)
    if a is None:
        parse_fail += 1; yes[r['set']].append(False); continue
    y = str(a.get('violation', '')).lower().startswith('y')
    yes[r['set']].append(y)
    if r['set'] == 'pos' and y:
        c = gt[r['clip']]
        if c['human_reliable']:
            code_ok.append(score_utils.code_match(a.get('code'), c['human'][0]['norm1']))
        t = vlm.to_sec(a.get('time_sec'))
        if t is not None:
            terr.append(abs(t + r['t0'] - r['label_t'] - 0.5))
for s in ('pos', 'pair_neg', 'off_neg', 'rand_neg'):
    print(f'{s:9} yes {sum(yes[s])}/{len(yes[s])}')
print(f'parse failures {parse_fail} | code agreement on reliable yes-positives {sum(code_ok)}/{len(code_ok)}')
if terr:
    print(f'time error |t - (label+0.5)| on yes-positives: median {st.median(terr):.1f}s, <=1s {sum(e <= 1 for e in terr)}/{len(terr)}, <=2s {sum(e <= 2 for e in terr)}/{len(terr)}')
ok = [r for r in res if not r['error']]
print(f'per-window total s: median {st.median(r["total_s"] for r in ok):.1f} max {max(r["total_s"] for r in ok):.1f} | '
      f'peak VRAM {max(r["peak_gb"] for r in ok):.1f} GB | in_tokens max {max(r["in_tokens"] for r in ok)} | errors {len(res) - len(ok)}')
