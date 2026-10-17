"""Type-specific discrimination from a verify_windows raw log (aggregates only).
pos: yes AND code matches the clip's human norm (mechanism-reliable clips).
pair_neg: yes AND code matches the norm of the paired violation clip in the same group (matched twin).
Usage: python -I verify_codes.py <repo_root> <tag>
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_utils import code_match  # noqa: E402

root, tag = sys.argv[1], sys.argv[2]
P = os.path.join(root, 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
norm_of_group = {c['group']: c['human'][0]['norm1'] for c in gt.values() if c['violation'] and c['human_reliable']}
n = {'pos': [0, 0], 'pair_neg': [0, 0]}
for line in open(os.path.join(P, 'vlm_raw', f'verify_{tag}.jsonl')):
    r = json.loads(line)
    s = r.get('set')
    if s not in n:
        continue
    want = norm_of_group.get(gt[r['clip']]['group'])
    if want is None:
        continue
    m = re.search(r'\{.*\}', r.get('text') or '', re.S)
    try:
        a = json.loads(m.group(0)) if m else {}
    except Exception:
        a = {}
    if 'violation' not in a:  # per-item prompt
        yes = [k for k, v in a.items() if str(v).lower().startswith('y') and re.match(r'^\d', k)]
        hit = any(code_match(k, want) for k in yes)
    else:
        hit = str(a.get('violation', '')).lower().startswith('y') and code_match(a.get('code'), want)
    n[s][0] += hit; n[s][1] += 1
print(f'{tag}: claims the reliable mechanism -> pos {n["pos"][0]}/{n["pos"][1]} | matched clean twin {n["pair_neg"][0]}/{n["pair_neg"][1]}')
