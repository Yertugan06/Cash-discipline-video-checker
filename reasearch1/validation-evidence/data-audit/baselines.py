"""Pixel-free baselines: leave-one-out duration verdict and relative-position timecode.
Input: output of meta.py (python3 -I meta.py data/open > meta.txt; python3 -I baselines.py meta.txt)."""
import math, re, statistics as st, sys

lab, vid = {}, {}
for line in open(sys.argv[1], encoding='utf-8'):
    if line.startswith('ROW'):
        r = eval(line[4:])
        if r[0].startswith('наим'):
            continue
        name, t = r[0].replace('Х', 'X'), None
        if len(r) == 3:
            m = re.findall(r'\d+', r[1])
            t = int(m[0]) * 60 + int(m[1]) if 'мин' in r[1] else int(m[0])
        lab[name] = t
    if line.startswith('VID'):
        p = line.split()
        vid[p[1].replace('Х', 'X')[:-4]] = (float(p[2]), float(p[4]), p[3])  # MB, duration, md5

seen, uniq = set(), []
for n in sorted(vid, key=lambda s: int(s[2:])):
    if vid[n][2] not in seen:
        seen.add(vid[n][2]); uniq.append(n)

correct = 0
for n in uniq:
    train = [m for m in uniq if m != n]
    _, th = max((sum((vid[m][1] <= th) == (lab[m] is not None) for m in train), th) for th in (vid[m][1] for m in train))
    correct += (vid[n][1] <= th) == (lab[n] is not None)
print(f'LOO duration-threshold verdict accuracy: {correct}/{len(uniq)}')

dur = [vid[n][1] for n in uniq]; br = [vid[n][0] * 8 / vid[n][1] for n in uniq]
print('Pearson(log duration, bitrate):', round(st.correlation([math.log(d) for d in dur], br), 3))

rows = [(n, lab[n], vid[n][1]) for n in vid if lab[n] is not None]
for tol in (1, 2, 3, 5):
    hit = sum(abs(st.median(tt / dd for m, tt, dd in rows if vid[m][2] != vid[n][2]) * d - t) <= tol for n, t, d in rows)
    print(f'relative-position timecode baseline within ±{tol}s: {hit}/{len(rows)}')
