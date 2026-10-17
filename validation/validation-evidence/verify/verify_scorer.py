#!/usr/bin/env python3
"""
Verify scorer correctness with synthetic predictions:
1. Perfect predictions at label times
2. All-clean predictions
3. All-violation with events at label+2.4 seconds
4. Empty events
5. Edge cases: N.0 vs N+0.5 convention, merged duplicates
"""

import json
import os

ROOT = "/home/yertugan/Repositories/hackathon"
P = os.path.join(ROOT, 'data', 'validation-private')

# Load ground truth
gt = json.load(open(os.path.join(P, 'gt.json')))

# Create test cases
def create_perfect_predictions():
    """Predictions exactly at organizer times"""
    pred = {}
    for cid, clip in gt.items():
        if clip['violation']:
            events = [{'t': t, 'code': None, 'conf': None} for t in clip['org_times']]
            pred[cid] = {
                'verdict': 'violation',
                'events': events,
                'runtime_s': 1.0,
                'error': None
            }
        else:
            pred[cid] = {
                'verdict': 'no_violation',
                'events': [],
                'runtime_s': 1.0,
                'error': None
            }
    return pred

def create_all_clean():
    """All clips predicted as clean"""
    return {cid: {'verdict': 'no_violation', 'events': [], 'runtime_s': 1.0, 'error': None}
            for cid in gt}

def create_all_violation():
    """All clips predicted as violations with events at label+2.4s"""
    pred = {}
    for cid, clip in gt.items():
        if clip['violation']:
            # Event at label+2.4s
            events = [{'t': t + 2.4, 'code': None, 'conf': None} for t in clip['org_times']]
        else:
            # False positive events
            events = [{'t': 10.0, 'code': None, 'conf': None}]
        pred[cid] = {
            'verdict': 'violation',
            'events': events,
            'runtime_s': 1.0,
            'error': None
        }
    return pred

def create_empty_events():
    """Predictions with empty event lists"""
    return {cid: {'verdict': clip['violation'] and 'violation' or 'no_violation',
                  'events': [], 'runtime_s': 1.0, 'error': None}
            for cid, clip in gt.items()}

# Create all test prediction sets
tests = {
    'perfect': create_perfect_predictions(),
    'all_clean': create_all_clean(),
    'all_violation': create_all_violation(),
    'empty_events': create_empty_events(),
}

# Save predictions
pred_dir = os.path.join(P, 'preds')
os.makedirs(pred_dir, exist_ok=True)

for name, pred in tests.items():
    fpath = os.path.join(pred_dir, f'verify_{name}.json')
    with open(fpath, 'w') as f:
        json.dump(pred, f)
    print(f"Created: {name} ({len(pred)} clips)")

print(f"\nNow run scorer to verify results:")
print(f"  cd /home/yertugan/Repositories/hackathon")
for name in tests:
    print(f"  /home/yertugan/.venvs/dt26/bin/python -I validation-evidence/harness/score.py /home/yertugan/Repositories/hackathon verify_{name}")
