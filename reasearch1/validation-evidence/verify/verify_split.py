#!/usr/bin/env python3
"""
Independent verification of split integrity:
- Check that duplicate pairs are in the same split
- Check that violation/clean pairs are in the same group (already checked by gt.py via union-find)
"""

import collections
import json
import os

ROOT = "/home/yertugan/Repositories/hackathon"
P = os.path.join(ROOT, 'data', 'validation-private')

# Load ground truth and split
gt = json.load(open(os.path.join(P, 'gt.json')))
split = json.load(open(os.path.join(P, 'split.json')))

print("=== Split Integrity Verification ===\n")

# Build groups -> clips mapping
groups = collections.defaultdict(list)
for clip_id, clip_data in gt.items():
    group_id = clip_data['group']
    groups[group_id].append(clip_id)

print(f"Total groups: {len(groups)}")
print(f"Total clips: {len(gt)}")

# Verify all clips in each group have the same split
split_violations = []
for group_id, clip_ids in groups.items():
    splits_in_group = [split[cid] for cid in clip_ids]
    if len(set(splits_in_group)) > 1:
        split_violations.append(f"  Group {group_id}: clips {clip_ids} have mixed splits {splits_in_group}")

if split_violations:
    print(f"Split violations found: {len(split_violations)}")
    for v in split_violations:
        print(v)
else:
    print("✓ All groups have consistent splits (no straddling)")

# Check duplicate pairs specifically
print(f"\nDuplicate pair checks:")
duplicates = [('X-4', 'X-47'), ('X-5', 'X-48')]
for a, b in duplicates:
    if a in gt and b in gt:
        a_split = split[a]
        b_split = split[b]
        a_group = gt[a]['group']
        b_group = gt[b]['group']
        match = a_split == b_split and a_group == b_group
        print(f"  {a} vs {b}: split={match} ({a_split}/{b_split}), group={a_group==b_group} ({a_group}/{b_group})")

# Check violation/clean pairs (any clips in same group should have same verdict)
verdict_violations = []
for group_id, clip_ids in groups.items():
    verdicts = [gt[cid]['violation'] for cid in clip_ids]
    if len(set(verdicts)) > 1:
        verdict_violations.append(f"  Group {group_id}: clips {clip_ids} have mixed verdicts")

if verdict_violations:
    print(f"\nVerdict violations found: {len(verdict_violations)}")
    for v in verdict_violations:
        print(v)
else:
    print("\n✓ All groups have consistent verdicts (no violation/clean pairs)")

# Summary
print(f"\n=== Summary ===")
print(f"Dev split: {sum(1 for cid in gt if split[cid] == 'dev')} clips")
print(f"Lockbox split: {sum(1 for cid in gt if split[cid] == 'lockbox')} clips")

dev_viol = sum(1 for cid in gt if split[cid] == 'dev' and gt[cid]['violation'])
dev_clean = sum(1 for cid in gt if split[cid] == 'dev' and not gt[cid]['violation'])
lockbox_viol = sum(1 for cid in gt if split[cid] == 'lockbox' and gt[cid]['violation'])
lockbox_clean = sum(1 for cid in gt if split[cid] == 'lockbox' and not gt[cid]['violation'])

print(f"  Dev: {dev_viol} violations, {dev_clean} clean")
print(f"  Lockbox: {lockbox_viol} violations, {lockbox_clean} clean")
print(f"  Verdict: reproduced" if not split_violations and not verdict_violations else "Verdict: contradicted")
