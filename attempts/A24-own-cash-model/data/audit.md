# A24 presence labels ready for D3

Manifest created at 2026-10-18 05:17:42 UTC, under one minute after this worker began. File: label-manifest.json. SHA-256: `28b2fccd248e3a7179c07ec17874f19d106f2a79184f285ba3756f1e9f47e255`.

Exactly12 real-frame labels:7 positive,5 negative. Schema1, source_commit4a3b9ea, task workspace_cash_presence. No absolute video paths, pixels or model predictions enter this manifest.

| Split | Positive clip@seconds | Negative clip@seconds | Total |
| --- | --- | --- | ---: |
| train | X38@30, X26@15, X10@8, X2@9.8, X14@60 | X23@16, X29@16, X32@2 | 8 |
| probe | X4@56, X13@30 | X33@2, X40@18 | 4 |

The11 A13 rows and original notes were read with ast.parse/ast.literal_eval from shared/a22/base/attempts/A13-detection-spike/scripts/spike_test.py; no source module was executed. X40@18 is a negative from the explicit user confirmation (coat and bag only). All labels refer to cash visible in the work area at that exact frame. Original notes are provenance only; do not use them as model features or legal/ownership labels.

Original video hashes come only from shared/a23/base/data/prepared/videos.jsonl. Its42 metadata rows include X4/X47 with the same SHA5385be9420e6a70547d6bcfd0b13d60f9c0738877645afa277d09550a96b8445, and X5/X48 with the same SHA1f5840bff58f298e89c4afa00cb1c18f6dafc5c4096c251d9b507604ebefe906. Duplicate-group hash consistency was checked. group_sha256 is the canonical original-video SHA, not a hash of a derived image. There are8 train groups,4 probe groups and0 overlaps. X47 must remain excluded from fitting as an alias of probe X4. All derived crops/augmentations inherit the original group and split, even if their image/video bytes differ.

Probe images must never enter fitting, normalization/feature statistics, threshold selection, augmentation fitting or model selection. This is a split held out from this fit only: all40 public clips previously influenced development, and the A13 samples were already used in model exploration. No blind or broadly held-out accuracy claim is justified.

These are frame-presence labels, not banknote boxes, cash ownership, loose-on-desk status or legal violations. A positive frame can contain many unrelated detector boxes. Never label every box or arbitrary crop in a positive frame as cash. Cropping can remove the cash: an ROI receives this label only if its coverage is independently justified; otherwise retain a full-frame/work-area image or leave that crop unknown. A negative exact frame does not label its neighboring timestamps or the entire video negative.

Validation actually run: generator completed, asserting the exact12 clip/time pairs, label polarity,8/4 memberships,5/3 train classes,2/2 probe classes, unique sample keys, valid64hex original SHA and0 group overlap. audit.json records source-file digests, counts and aliases. Ruff check passed after formatting. No decode, model load, inference, training, GPU, dependency or production change occurred.

Exact rerun from worker-2:

```bash
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python attempts/A24-own-cash-model/data/build_manifest.py --a13 /home/ubuntu/workspaces/datathon26-workers/shared/a22/base/attempts/A13-detection-spike/scripts/spike_test.py --videos /home/ubuntu/workspaces/datathon26-workers/shared/a23/base/data/prepared/videos.jsonl --out attempts/A24-own-cash-model/data
```

Changed files are this audit, audit.json, label-manifest.json, build_manifest.py and progress.md. Parent transfers label-manifest.json directly to D3. No blocker for this data handoff; training/measurement belongs to D3.
