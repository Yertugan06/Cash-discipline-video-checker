"""In-sample reference: always output the K most frequent human norm codes (an upper-bound shortcut, not a system)."""
import collections, json, os, sys
sys.argv = [sys.argv[0], sys.argv[1]]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'arch_mechanism_match.py')).read().split('for name in sys.argv')[0]
ns = {'__name__': 'x'}; exec(src, ns)
gt, pairs, match = ns['gt'], ns['pairs'], ns['match']
rel = [k for k in gt if gt[k]['violation'] and gt[k]['human_reliable']]
top = [x for x, _ in collections.Counter(gt[k]['human'][0]['norm1'] for k in rel).most_common(3)]
for K in (1, 2, 3):
    s = set().union(*[pairs(x) for x in top[:K]])
    print(f'constant top-{K} most frequent codes (in-sample): {sum(match(s, pairs(gt[k]["human"][0]["norm1"])) for k in rel)}/{len(rel)}')
