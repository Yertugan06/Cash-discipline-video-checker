import re, sys, statistics as st
lab = {}; vids = {}
for line in open(sys.argv[1], encoding='utf-8'):
    if line.startswith('ROW'):
        r = eval(line[4:])
        if r[0].startswith('наим'): continue
        name = r[0].replace('Х', 'X'); t = None
        if len(r) == 3:
            m = re.findall(r'\d+', r[1]); t = int(m[0]) * 60 + int(m[1]) if 'мин' in r[1] else int(m[0])
        lab[name] = t
    if line.startswith('VID'):
        p = line.split(); name = p[1].replace('Х', 'X')[:-4]
        vids[name] = dict(mb=float(p[2]), md5=p[3], dur=float(p[4]))
seen = {}; uniq = []
for n in sorted(vids, key=lambda s: int(s[2:])):
    v = vids[n]
    if v['md5'] in seen: print('DUP', n, '==', seen[v['md5']], 'labels', lab[n], lab[seen[v['md5']]]); continue
    seen[v['md5']] = n; uniq.append(n)
V = [n for n in uniq if lab[n] is not None]; C = [n for n in uniq if lab[n] is None]
print('unique', len(uniq), 'viol', len(V), 'clean', len(C))
for name, g in (('viol', V), ('clean', C)):
    d = [vids[n]['dur'] for n in g]; br = [vids[n]['mb'] * 8 / vids[n]['dur'] for n in g]
    print(name, 'dur min/med/max/sum', min(d), st.median(d), max(d), round(sum(d), 1), 'Mbps med', round(st.median(br), 3), 'min/max', round(min(br), 3), round(max(br), 3))
    print('  >30s:', sum(x > 30 for x in d), ' <=20s:', sum(x <= 20 for x in d))
# best duration threshold
allv = [(vids[n]['dur'], lab[n] is not None) for n in uniq]
best = max(((sum((d <= th) == y for d, y in allv), th) for th in sorted(d for d, _ in allv)))
print('best dur threshold acc', best[0], '/', len(allv), 'at <=', best[1])
allb = [(vids[n]['mb'] * 8 / vids[n]['dur'], lab[n] is not None) for n in uniq]
for sign in (1, -1):
    b = max(((sum(((x - th) * sign <= 0) == y for x, y in allb), th) for th in sorted(x for x, _ in allb)))
    print('best bitrate threshold acc sign', sign, b)
# label positions (all rows incl. both dup labels)
rows = [(n, lab[n], vids[n]['dur']) for n in vids if lab[n] is not None]
print('label rows', len(rows))
for n, t, d in sorted(rows, key=lambda r: r[1]): print(f'  {n}: t={t} dur={d} rel={t/d:.2f} remaining={d-t:.1f}')
ts = [t for _, t, _ in rows]
print('t<=10', sum(t <= 10 for t in ts), 't<=20', sum(t <= 20 for t in ts), 'median', st.median(ts))
print('total unique min', round(sum(vids[n]['dur'] for n in uniq) / 60, 2))
