#!/usr/bin/env python3
"""
Proper leave-one-out (LOO) cross-validation for duration threshold baseline.
For each test clip, train threshold on all other clips and test on that one.
"""

import json
import os
import re
import struct

ROOT = "/home/yertugan/Repositories/hackathon"
P = os.path.join(ROOT, 'data', 'validation-private')

gt = json.load(open(os.path.join(P, 'gt.json')))

def parse_mov_duration(fpath):
    """Extract duration from MOV file by parsing atom structure"""
    def atoms(f, start, end):
        f.seek(start)
        while f.tell() < end:
            pos = f.tell()
            h = f.read(8)
            if len(h) < 8:
                break
            size, typ = struct.unpack('>I4s', h)
            hdr = 8
            if size == 1:
                size = struct.unpack('>Q', f.read(8))[0]
                hdr = 16
            elif size == 0:
                size = end - pos
            yield typ.decode('latin1'), pos, pos + hdr, pos + size
            f.seek(pos + size)

    out = {}
    try:
        with open(fpath, 'rb') as f:
            end = os.path.getsize(fpath)
            for t, p, d, e in atoms(f, 0, end):
                if t == 'moov':
                    for t2, p2, d2, e2 in atoms(f, d, e):
                        if t2 == 'mvhd':
                            f.seek(d2)
                            ver = f.read(1)[0]
                            f.read(3)
                            if ver == 1:
                                f.read(16)
                                ts, dur = struct.unpack('>IQ', f.read(12))
                            else:
                                f.read(8)
                                ts, dur = struct.unpack('>II', f.read(8))
                            out['dur'] = dur / ts
                    break
    except:
        pass
    return out.get('dur')

# Extract durations
durations = {}
vdir = os.path.join(ROOT, 'data', 'open', 'videos')
for fname in os.listdir(vdir):
    if fname.endswith('.mov'):
        normalized = fname.replace('Х', 'X').replace('х', 'X').replace('x', 'X')
        m = re.search(r'X\s*-?\s*(\d+)', normalized)
        if m:
            clip_id = f"X-{int(m.group(1))}"
            fpath = os.path.join(vdir, fname)
            dur = parse_mov_duration(fpath)
            if dur is not None:
                durations[clip_id] = dur

print(f"=== Duration Threshold LOO Cross-Validation ===\n")

# LOO: for each test clip, find best threshold on other clips
loo_correct = 0
test_clips = [cid for cid in gt if cid in durations]

for test_id in test_clips:
    # Train on all other clips
    train_ids = [c for c in test_clips if c != test_id]
    train_viol = [durations[c] for c in train_ids if gt[c]['violation']]
    train_clean = [durations[c] for c in train_ids if not gt[c]['violation']]

    if not train_viol or not train_clean:
        continue

    # Find best threshold on training set
    best_thresh = None
    best_train_acc = 0

    for thresh in [i * 0.1 for i in range(int(min(train_clean) * 10) - 10, int(max(train_viol) * 10) + 10)]:
        train_acc = (
            sum(1 for d in train_viol if d < thresh) +
            sum(1 for d in train_clean if d >= thresh)
        )
        if train_acc > best_train_acc:
            best_train_acc = train_acc
            best_thresh = thresh

    # Test on this clip
    test_dur = durations[test_id]
    pred_viol = test_dur < best_thresh
    true_viol = gt[test_id]['violation']

    if pred_viol == true_viol:
        loo_correct += 1

print(f"LOO accuracy: {loo_correct}/{len(test_clips)} ({loo_correct*100/len(test_clips):.0f}%)")
print(f"Expected: 25/40")

if loo_correct == 25:
    print("✓ Matches expected claim!")
else:
    print(f"✗ Does not match (got {loo_correct}, expected 25)")
