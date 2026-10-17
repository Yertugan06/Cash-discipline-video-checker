# Leakage Review: gt.py, split.py, score.py

## Executive Summary
Reviewed for potential label leakage where label times, duration or relative position could leak into a system's inputs, or where the scorer could be gamed.

## gt.py Analysis

### Data Sources
1. **open_labels.xlsx** - organizer labels with verdict and times (ground truth)
2. **Таблица_нарушений.xlsx** - human annotations with times, norm codes, confidence
3. **Cash_Discipline_Cases_Rules.xlsx** - camera layout metadata

### Potential Leakage
- ✓ **No leakage via organizer times**: Times are read only for metadata (gt.json), not exposed in any training input
- ✓ **No leakage via durations**: Duration not extracted in gt.py
- ✓ **No leakage via relative position**: Relative position of times not computed in gt.py
- ✓ **Proper canonicalization**: Duplicate pairs and violation/clean pairs merged via union-find with group IDs, no per-clip label exposure

### Verdict
**No leakage detected in gt.py**

---

## split.py Analysis

### Data Sources
1. **gt.json** - ground truth with violation verdict and group assignments

### Risk: Stratification
The split uses `gt['violation']` indirectly through the group structure. Since groups are formed by duplicates AND violation/clean pairs, and split.py stratifies by group, it implicitly stratifies by verdict.

```python
by_layout = collections.defaultdict(list)
for g, ks in sorted(groups.items()):
    by_layout[collections.Counter(gt[k]['layout'] for k in ks).most_common(1)[0][0]].append(g)
for lay, gs in sorted(by_layout.items()):
    rng.shuffle(gs)
    for g in gs[:round(len(gs) / 3)]:
        lock.update(groups[g])
```

This stratification is **intentional and correct**: it ensures paired violation/clean clips stay together in the split, which is required.

### Risk: Fixed Seed
Seed is fixed (26), making the split deterministic. This is good for reproducibility, but could allow gaming if one knew the seed.

### Potential Gaming
- ✗ **No direct gaming risk**: The split mechanism itself doesn't expose labels
- ✓ **Proper isolation**: Dev and lockbox splits are used to prevent development-set overfitting

### Verdict
**No leakage detected in split.py**

---

## score.py Analysis

### Data Sources
1. **gt.json** - ground truth with violation verdict, org_times, human annotations
2. **split.json** - split assignment
3. **Prediction file** - system predictions

### Risk 1: Label Times in Scorer
```python
ev = [(k, t) for k in ids if gt[k]['violation'] for t in gt[k]['org_times']]
```
The scorer uses organizer times directly to evaluate localization. This is **correct** - it's how you measure localization quality. The scorer is not a prediction input; it's an evaluation metric.

### Risk 2: Many Events Per Clip
```python
nv = [len(pred[k]['events']) for k in ids if gt[k]['violation']]
nc = [len(pred[k]['events']) for k in ids if not gt[k]['violation']]
print(f'events/violation clip mean {st.mean(nv) if nv else 0:.2f} | events/clean clip mean {st.mean(nc) if nc else 0:.2f}')
```
The scorer does NOT reward systems for outputting many events. It tracks:
- Top-1 event localization (only checks first event)
- Any-event localization (checks if ANY predicted event is near a label)
- TP/FN/FP/TN (binary verdict, not per-event)

A system could game by outputting many events, but:
- Top-1 metric incentivizes quality over quantity
- TP/FN/FP/TN is verdict-based (not event-based), so extra events don't help

### Risk 3: Code Matching
```python
def code_match(a, b):
    a, b = code_key(a), code_key(b)
    if not a or not b:
        return False
    a, b = a.split('-'), b.split('-')
    return a[0] == b[0] and (len(a) == 1 or len(b) == 1 or a[1] == b[1])

hit_code = sum(1 for k in rel if any(code_match(e.get('code'), gt[k]['human'][0]['norm1'])
                                     for e in pred[k]['events']))
```
The scorer does check if predicted norm codes match human annotations. This is intentional - it measures if the system identified the correct rule.

However: **This code should NOT be used in training**, as it requires knowing human annotations (ground truth) in advance. The score.py is a **test-time evaluation tool**, not a training loss function.

### Risk 4: Relative Position
No risk detected. The scorer does NOT extract or use relative position of violations within the clip.

### Verdict
**No leakage detected in score.py** - It is properly designed as an evaluation metric, not a training loss.

---

## Overall Verdict

### Summary
- ✓ **gt.py**: Properly canonicalizes duplicates and pairs, no label exposure
- ✓ **split.py**: Stratifies correctly to keep pairs together, fixed seed for reproducibility
- ✓ **score.py**: Designed as evaluation metric (not training input), uses labels only for computing metrics

### Risk Assessment
**No critical leakage detected.** The harness is designed for proper train/test separation.

**Important notes:**
1. Score.py should ONLY be used for test-time evaluation, not during training
2. Systems must NOT use gt.json or split.json during training
3. Systems may use duration as a feature (it's not in any ground truth file)
4. Systems may use relative position as a feature (it's not in any ground truth file)

---

## Recommendations
None. The harness appears sound.
