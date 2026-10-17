#!/usr/bin/env python3
"""
Further investigation of baseline discrepancy.
Check if relative position results change when:
1. Excluding one of the duplicate pairs
2. Using different median calculation
3. Using different event subset
"""

import json
import os

ROOT = "/home/yertugan/Repositories/hackathon"
P = os.path.join(ROOT, 'data', 'validation-private')

gt = json.load(open(os.path.join(P, 'gt.json')))

print("=== Baseline Investigation ===\n")

# All violation events
events_all = [(cid, t) for cid in gt if gt[cid]['violation'] for t in gt[cid]['org_times']]
times_all = [t for _, t in events_all]

print(f"All violation events: {len(events_all)} events")
print(f"  Times: {sorted(times_all)}")

# Try different exclusions
for exclude_clip in ['X-4', 'X-5', 'X-47', 'X-48', None]:
    events = [(cid, t) for cid, t in events_all if cid != exclude_clip]
    times = [t for _, t in events]

    if not times:
        continue

    median = sorted(times)[len(times) // 2]

    counts = {k: sum(1 for t in times if abs(t - median) <= k) for k in (1, 2, 3, 5)}

    label = f"excluding {exclude_clip}" if exclude_clip else "all events"
    print(f"\n{label}: n={len(events)}, median={median:.1f}s")
    print(f"  ±1/2/3/5s: {counts[1]}/{counts[2]}/{counts[3]}/{counts[5]}")

print(f"\nExpected claim: 4/9/12/18 of 22")
print(f"Our results: 4/5/7/10 of 22")

# Try different medians (maybe they used a different percentile)
print(f"\nTrying different percentiles as 'median':")
for percentile in [0, 25, 50, 75, 100]:
    idx = min(int(len(times_all) * percentile / 100), len(times_all) - 1)
    t_percentile = sorted(times_all)[idx]

    counts = {k: sum(1 for t in times_all if abs(t - t_percentile) <= k) for k in (1, 2, 3, 5)}
    print(f"  {percentile}th percentile ({t_percentile:.1f}s): {counts[1]}/{counts[2]}/{counts[3]}/{counts[5]}")

# Check if maybe it's not median time but modal (most frequent relative position range)
print(f"\nEvent time distribution:")
import collections
time_counts = collections.Counter(times_all)
for t in sorted(time_counts.keys()):
    print(f"  {t:.1f}s: {time_counts[t]}")

# Maybe the claim is using a different definition of "within ±k seconds"
# For instance, maybe each event independently matches if any other event is within ±k
print(f"\nAlternative: count events that have a match within ±k of ANY other event:")
for k in (1, 2, 3, 5):
    matched = set()
    for i, t1 in enumerate(times_all):
        for j, t2 in enumerate(times_all):
            if i != j and abs(t1 - t2) <= k:
                matched.add(i)
    print(f"  ±{k}s: {len(matched)}/{len(times_all)}")
