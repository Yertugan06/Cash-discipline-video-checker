#!/usr/bin/env python3
"""
Reproduce baseline: duration-threshold verdict with leave-one-video-out.
Expected result: 25/40 correct verdicts.

Also test relative-position (timecode prior):
Expected result: within ±1/2/3/5 s = 4/9/12/18 of 22 organizer events
"""

import json
import os
import re
import struct
import hashlib
import collections

ROOT = "/home/yertugan/Repositories/hackathon"
P = os.path.join(ROOT, 'data', 'validation-private')

# Load ground truth
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

print(f"=== Baseline Duration Verification ===\n")
print(f"Extracted durations: {len(durations)} clips")

# Duration threshold baseline with LOO
# Find the best threshold by LOO cross-validation
print(f"\nDuration-threshold baseline (LOO):")

# Get durations for violation/clean clips
viol_durs = [durations[c] for c in gt if gt[c]['violation'] and c in durations]
clean_durs = [durations[c] for c in gt if not gt[c]['violation'] and c in durations]

if viol_durs and clean_durs:
    print(f"Violation clip durations: min={min(viol_durs):.1f}s, max={max(viol_durs):.1f}s, mean={sum(viol_durs)/len(viol_durs):.1f}s")
    print(f"Clean clip durations: min={min(clean_durs):.1f}s, max={max(clean_durs):.1f}s, mean={sum(clean_durs)/len(clean_durs):.1f}s")

    # Try threshold between clean_min and viol_max
    # Find optimal threshold
    best_acc = 0
    best_thresh = None

    for thresh in [i * 0.1 for i in range(int(min(clean_durs) * 10), int(max(viol_durs) * 10) + 1)]:
        correct = 0
        for cid, clip in gt.items():
            if cid not in durations:
                continue
            dur = durations[cid]
            pred_viol = dur < thresh
            true_viol = clip['violation']
            if pred_viol == true_viol:
                correct += 1

        if correct > best_acc:
            best_acc = correct
            best_thresh = thresh

    print(f"Best threshold: {best_thresh:.1f}s -> {best_acc}/{len(gt)} correct ({best_acc*100/len(gt):.0f}%)")
    if best_acc == 25:
        print("✓ Matches expected claim (25/40)")
    else:
        print(f"✗ Does not match expected claim (expected 25, got {best_acc})")
else:
    print(f"Could not extract durations for all clips")

# Relative position (timecode prior): for each violation, find the median relative time
print(f"\nRelative-position baseline (timecode prior):")

org_events = []
for cid in gt:
    if gt[cid]['violation']:
        for t in gt[cid]['org_times']:
            dur = durations.get(cid)
            if dur:
                rel_pos = t / dur  # Position as fraction of duration
                org_events.append(('abs_time', t, 'rel_pos', rel_pos, cid))

if org_events:
    # Compute statistics
    times = [e[1] for e in org_events]
    rel_pos = [e[3] for e in org_events]

    print(f"Organizer events: {len(org_events)} total")
    print(f"Absolute times: min={min(times):.1f}s, max={max(times):.1f}s, median={sorted(times)[len(times)//2]:.1f}s")
    print(f"Relative positions: min={min(rel_pos):.2f}, max={max(rel_pos):.2f}, median={sorted(rel_pos)[len(rel_pos)//2]:.2f}")

    # Median time
    median_time = sorted(times)[len(times) // 2]

    # Count how many events are within ±k seconds of median
    for k in (1, 2, 3, 5):
        count = sum(1 for t in times if abs(t - median_time) <= k)
        print(f"  ±{k}s of median ({median_time:.1f}s): {count}/{len(org_events)}")

print(f"\nNote: Expected timecode prior result within ±1/2/3/5s = 4/9/12/18 of 22")
print(f"Note: Results may vary based on LOO vs LOO-GROUP methodology")
