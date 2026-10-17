#!/usr/bin/env python3
"""
Independent verification of ground truth:
- Unique videos (expected 40)
- Violation/clean split (expected 21/19)
- Organizer events (expected 22)
- Duplicate pairs (claimed: X-4≡X-47 and X-5≡X-48)
- Check gt.json matches
"""

import collections
import hashlib
import json
import os
import re
import sys

import openpyxl

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/home/yertugan/Repositories/hackathon"

# ---- Extract video files and compute MD5 ----
vdir = os.path.join(ROOT, 'data', 'open', 'videos')
files = {}
md5s = {}

for fname in os.listdir(vdir):
    if fname.endswith('.mov'):
        # Normalize clip IDs: replace Cyrillic X with Latin X
        normalized = fname.replace('Х', 'X').replace('х', 'X').replace('x', 'X')
        m = re.search(r'X\s*-?\s*(\d+)', normalized)
        if m:
            clip_id = f"X-{int(m.group(1))}"
            fpath = os.path.join(vdir, fname)
            files[clip_id] = fpath
            # Compute MD5
            with open(fpath, 'rb') as f:
                md5s[clip_id] = hashlib.md5(f.read()).hexdigest()

print(f"== Ground Truth Verification ==")
print(f"Total video files found: {len(files)}")
print(f"Video IDs: {sorted(files.keys())}")

# ---- Read organizer labels from open_labels.xlsx ----
org_labels = {}
wb = openpyxl.load_workbook(
    os.path.join(ROOT, 'data', 'open', 'open_labels.xlsx'),
    read_only=True,
    data_only=True
)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))

for r in rows[1:]:  # Skip header
    if not r or not r[0]:
        continue
    cid_raw = str(r[0]).strip().replace('Х', 'X').replace('х', 'X').replace('x', 'X')
    m = re.search(r'X\s*-?\s*(\d+)', cid_raw)
    if not m:
        continue
    cid = f"X-{int(m.group(1))}"

    # Determine violation status
    is_violation = False
    times = []

    # Check columns 1+ for violation keyword and time
    for col_idx, cell_val in enumerate(r[1:], 1):
        if cell_val is None or cell_val == '':
            continue
        cell_str = str(cell_val).lower()

        # Check for violation keyword (has 'наруш' but not 'без')
        if 'наруш' in cell_str and 'без' not in cell_str:
            is_violation = True

        # Extract times (integers or floats from the cell)
        for match in re.finditer(r'\d+(?:[.,]\d+)?', str(cell_val)):
            times.append(float(match.group().replace(',', '.')))

    # Violation if times found or marked
    if times:
        is_violation = True

    org_labels[cid] = {
        'violation': is_violation,
        'times': sorted(list(set(times)))  # Unique times, sorted
    }

print(f"Organizer labels loaded: {len(org_labels)} clips")

# ---- Identify duplicates by MD5 ----
by_md5 = collections.defaultdict(list)
for cid, fpath in files.items():
    h = md5s[cid]
    by_md5[h].append(cid)

print(f"\nDuplicate groups by MD5:")
for h, cids in sorted(by_md5.items(), key=lambda x: min(int(c.split('-')[1]) for c in x[1])):
    if len(cids) > 1:
        print(f"  {sorted(cids)}")

# Check claimed duplicates
print(f"\nDuplicate pair checks:")
print(f"  X-4 and X-47 same file? {md5s.get('X-4') == md5s.get('X-47')}")
print(f"  X-5 and X-48 same file? {md5s.get('X-5') == md5s.get('X-48')}")

# ---- Verify with gt.json ----
gt_path = os.path.join(ROOT, 'data', 'validation-private', 'gt.json')
if os.path.exists(gt_path):
    with open(gt_path) as f:
        gt = json.load(f)

    print(f"\nGround truth JSON verification:")
    print(f"  Clips in gt.json: {len(gt)}")

    # Check violation counts
    violations = [c for cid, c in gt.items() if c['violation']]
    clean = [c for cid, c in gt.items() if not c['violation']]
    print(f"  Violations: {len(violations)}")
    print(f"  Clean: {len(clean)}")

    # Count organizer events
    org_events = sum(len(c['org_times']) for c in violations)
    print(f"  Total organizer events (across violations): {org_events}")

    # Check for mismatches with our org_labels
    mismatches = []
    for cid, gt_clip in gt.items():
        if cid in org_labels:
            org_our = org_labels[cid]
            gt_our = gt_clip

            # Check violation flag
            if org_our['violation'] != gt_our['violation']:
                mismatches.append(f"  {cid}: violation mismatch (ours={org_our['violation']}, gt={gt_our['violation']})")

            # Check times (should be exact match for organizer times)
            if sorted(org_our['times']) != sorted(gt_our['org_times']):
                mismatches.append(f"  {cid}: times mismatch (ours={org_our['times']}, gt={gt_our['org_times']})")

    if mismatches:
        print(f"  Mismatches found: {len(mismatches)}")
        for m in mismatches:
            print(m)
    else:
        print(f"  No mismatches with gt.json")

    # Check duplicate groups
    print(f"\nGround truth group structure:")
    groups = collections.defaultdict(list)
    for cid, c in gt.items():
        groups[c['group']].append(cid)

    print(f"  Total groups: {len(groups)}")
    size_hist = collections.Counter(len(cids) for cids in groups.values())
    print(f"  Size histogram: {dict(size_hist)}")

else:
    print("gt.json not found!")

print("\n=== Summary ===")
print(f"Unique clips: {len(files)}")
print(f"Violations: {sum(1 for c in org_labels.values() if c['violation'])}")
print(f"Clean: {sum(1 for c in org_labels.values() if not c['violation'])}")
print(f"Total organizer event times: {sum(len(c['times']) for c in org_labels.values() if c['violation'])}")
