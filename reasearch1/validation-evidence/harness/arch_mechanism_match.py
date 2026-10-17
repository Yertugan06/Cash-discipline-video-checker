import json, re, sys
P = sys.argv[1]
gt = json.load(open(P + '/gt.json'))
def pairs(s):
    """All (clause, sub) pairs in a code string, ignoring the document number."""
    s = str(s or '')
    out = set()
    m = re.match(r'^(\d+)-(\d+)(?:-(\d+))?', s)
    if m:
        out.add((m.group(2), m.group(3)))
    for c, sub in re.findall(r'п\.\s*(\d+)(?:\s*\((\d+)\)|\s*пп\.\s*(\d+)|\s*ч\.\s*(\d+))?', s) and [(x[0], x[1]) for x in re.findall(r'п\.\s*(\d+)(?:\s*\((\d+)\))?', s)] or []:
        out.add((c, sub or None))
    for c, sub in re.findall(r'п\.\s*(\d+)\s*(?:пп|ч)\.\s*(\d+)', s):
        out.add((c, sub))
    return out
def match(a, b):
    return any(x[0] == y[0] and (not x[1] or not y[1] or x[1] == y[1]) for x in a for y in b)
for name in sys.argv[2:]:
    pred = json.load(open(f'{P}/preds/{name}.json'))
    rel = [k for k in gt if gt[k]['violation'] and gt[k]['human_reliable']]
    any_hit = loc_hit = top_hit = 0
    for k in rel:
        g = pairs(gt[k]['human'][0]['norm1'])
        evs = pred[k]['events']
        ok = [e for e in evs if match(pairs(e.get('code')) | set().union(*[pairs(c) for c in e.get('codes', [])] or [set()]), g)]
        any_hit += bool(ok)
        loc_hit += any(min(abs(e['t'] - t) for t in gt[k]['org_times']) <= 3 for e in ok)
        top_hit += bool(evs) and evs[0] in ok
    print(f'{name}: mechanism (n={len(rel)}) any {any_hit}, any within ±3s {loc_hit}, top-1 code {top_hit}')
