"""Grouped dev/lockbox split. Unit = group (duplicates + violation/clean pairs), so a staged scenario
and its matched counterpart never straddle the split. Stratified by camera layout. Seed fixed.
Writes data/validation-private/split.json; prints counts only."""
import collections, json, os, random, sys

ROOT = sys.argv[1]
P = os.path.join(ROOT, 'data', 'validation-private')
gt = json.load(open(os.path.join(P, 'gt.json')))
groups = collections.defaultdict(list)
for k, c in gt.items():
    groups[c['group']].append(k)

rng = random.Random(26)
lock = set()
by_layout = collections.defaultdict(list)
for g, ks in sorted(groups.items()):
    by_layout[collections.Counter(gt[k]['layout'] for k in ks).most_common(1)[0][0]].append(g)
for lay, gs in sorted(by_layout.items()):
    rng.shuffle(gs)
    for g in gs[:round(len(gs) / 3)]:
        lock.update(groups[g])

split = {k: ('lockbox' if k in lock else 'dev') for k in gt}
json.dump(split, open(os.path.join(P, 'split.json'), 'w'), indent=1)
print(dict(collections.Counter((split[k], gt[k]['violation']) for k in gt)))
print(dict(collections.Counter((split[k], gt[k]['layout']) for k in gt)))
