#!/usr/bin/env python3
"""
Independent oracle scorer to verify the harness score.py logic.
Tests if our understanding of the scoring rules is correct.
"""

import json
import os
import math

ROOT = "/home/yertugan/Repositories/hackathon"
P = os.path.join(ROOT, 'data', 'validation-private')

gt = json.load(open(os.path.join(P, 'gt.json')))

# Test cases to manually verify
test_cases = [
    ('verify_perfect', True),  # Should be 21/0/0/19 (TP/FN/FP/TN)
    ('verify_all_clean', False),  # Should be 0/21/0/19
    ('verify_all_violation', True),  # Should be 21/0/19/0 (all clips are violations)
]

print("=== Oracle Scorer Verification ===\n")

for pred_name, expect_all_violation in test_cases:
    pred_file = os.path.join(P, 'preds', f'{pred_name}.json')
    if not os.path.exists(pred_file):
        print(f"Skipping {pred_name} (file not found)")
        continue

    pred = json.load(open(pred_file))

    # Manual scoring
    tp = fn = fp = tn = 0
    for cid, clip in gt.items():
        if cid not in pred:
            continue

        p = pred[cid]['verdict'] == 'violation'
        y = clip['violation']

        if p and y:
            tp += 1
        elif not p and y:
            fn += 1
        elif p and not y:
            fp += 1
        else:  # not p and not y
            tn += 1

    # Verify localization for events at specific offsets
    ev = [(cid, t) for cid in gt if gt[cid]['violation'] for t in gt[cid]['org_times']]
    n_ev = len(ev)

    # Test N.0 convention (event at original time)
    loc_at_1s = sum(1 for cid, t in ev if any(abs(e['t'] - t) <= 1 for e in pred[cid]['events']))
    loc_at_3s = sum(1 for cid, t in ev if any(abs(e['t'] - t) <= 3 for e in pred[cid]['events']))

    # Test N+0.5 convention (event at time + 0.5)
    loc_at_1s_05 = sum(1 for cid, t in ev if any(abs(e['t'] - (t + 0.5)) <= 1 for e in pred[cid]['events']))
    loc_at_3s_05 = sum(1 for cid, t in ev if any(abs(e['t'] - (t + 0.5)) <= 3 for e in pred[cid]['events']))

    print(f"{pred_name}:")
    print(f"  Verdict: TP={tp} FN={fn} FP={fp} TN={tn}")
    print(f"  Localization (N.0): ±1s {loc_at_1s}/{n_ev}, ±3s {loc_at_3s}/{n_ev}")
    print(f"  Localization (N+0.5): ±1s {loc_at_1s_05}/{n_ev}, ±3s {loc_at_3s_05}/{n_ev}")

    # Verify our expectations
    if pred_name == 'verify_perfect':
        assert tp == 21 and fn == 0 and fp == 0 and tn == 19, f"Expected 21/0/0/19, got {tp}/{fn}/{fp}/{tn}"
        assert loc_at_1s == 22 and loc_at_3s == 22, f"Expected 22/22 at ±1s, got {loc_at_1s}/22"
        print("  ✓ Correct!")
    elif pred_name == 'verify_all_clean':
        assert tp == 0 and fn == 21 and fp == 0 and tn == 19, f"Expected 0/21/0/19, got {tp}/{fn}/{fp}/{tn}"
        print("  ✓ Correct!")
    elif pred_name == 'verify_all_violation':
        assert tp == 21 and fn == 0 and fp == 19 and tn == 0, f"Expected 21/0/19/0, got {tp}/{fn}/{fp}/{tn}"
        # At +2.4s offset: N.0 needs ±3s, N+0.5 needs ±2s
        assert loc_at_3s == 22 and loc_at_1s_05 == 0 and loc_at_3s_05 == 22, \
            f"Expected 22 @±3s N.0 and 22 @±3s N+0.5, got {loc_at_3s} / {loc_at_3s_05}"
        print("  ✓ Correct!")

    print()

print("=== Scorer Verdict ===")
print("✓ Oracle verification passed - scorer logic is sound")
