# A25 TRAINED — reject promotion

Actual CPU runtime 9.301 s, exit 0. Train-only LOCO selected lambda 0.01; all32 folds held out all6 transforms of one clip. A24 feature order proven from hash-matched source and all8 reproduced training scores; every A24 file remains byte-identical.

A24 train: TP1/7 unknown. A25 train: TP4/TN3/1 positive unknown. A24 and A25 probe: TP1/3 unknown (1 positive,2 negative). No new probe decision benefit, thresholds unchanged, no promotion or LLM-context adapter. All40 public development and A24 probes already seen.

Code: run.py, preregistration: PREREGISTER.md, exact CPU argv: cpu-command.json. Actual outputs: artifacts/run-01/head.json, selection.json (all32 folds), report.json (all12 rows), a24-before.json (byte-identity proof).
