# A23: new main, synthetic clips and real mirrors

Published on 2026-10-18 at **http://localhost:8103**:

- [Three synthetic clips](http://localhost:8103/?run=a23-synthetic): all completed;
  all returned `no_violation`. Expected labels are unknown, so accuracy is unscored.
  Scene calibration was missing or incomplete. Wall times: 32.95, 14.16, 18.18 s.
- [Eight mirrored clips](http://localhost:8103/?run=a23-mirrored): **5/8 verdict
  agreement**, TP1 / TN4 / FN3 / FP0. X4, X13 and X20 were missed. X11 matched the
  violation label through an unsupported outsider finding; its annotated laptop
  violation was not established. This does not demonstrate improved reasoning.
- [Evaluation](http://localhost:8103/evaluation) keeps the original A21 audit and
  adds separate A22–A25 experiment reports. A classifier probe is not a video run.

The checker ran main `4a3b9ea`, automatic camera calibration, default overrides and
local safe-only Qwen3-VL-4B. Both batches used fresh perception on actual input
bytes, not mirrored detection coordinates. All eleven jobs completed their planned
0.5 s frame sampling, with no failed samples or whole-job deadlines. Some VLM
checks timed out or exhausted their budgets: full sampling is not full certainty.
Mirror times: median 63.11 s, maximum 150.94 s, total 620.52 s.

Mirrors are a selected four-positive/four-clean subset: X4/5, X11/12, X13/14,
X20/21. They are transforms of public development videos, not independent scenes
or a held-out camera test. CSV norm IDs and timestamps do not validate reasons.
The same eight saved A21 originals all predicted `no_violation` (4/8 agreement).
That comparison also changes source revision, so it does not isolate mirroring.

Production remains one VM, datathon2. Parallel datathon3 inference was used for
evaluation only and stopped after publishing the completed results. All eleven
videos and their traces were checked through the localhost tunnel. The original
42 live items, 42 annotations and 42 descriptions were preserved. Temporary door
review on 8104 and obsolete worker monitors were stopped.

The realtime overlay adds explicit attempt/source metadata and persistent upload
replay. Actual verification: **23 gateway tests passed**, frontend checks passed,
all eleven video range requests and trace endpoints succeeded. No manual browser
inspection is claimed. Raw API results, evidence images and videos stay on the
authorized VMs; only allowlisted numeric/text outputs are collected here.

See `synthetic-results/summary.jsonl`, `mirror-results/summary.jsonl`,
`mirrors/manifest.json`, `mirrors/scoring-truth.json` and publication reports.
Human observations and expected labels never enter the uploaded model input.

Per-frame numeric traces remain local and are excluded from Git. Summaries,
source pins, manifests, scorer code and decisions are retained in the repository.
The teammate's later before/moment/after evidence change (`d0d7f0a`) was merged
after these tests; all four focused evidence tests passed. It did not change the
recorded A23 verdicts or their source revision.

Final deployment: application revision `bc67950` includes that evidence feature
for future jobs. The checker restarted only after confirming zero active jobs;
health and readiness both returned200. Existing saved results were retained.
The local4B safe checks and automatic/default camera configuration are unchanged.
See `application-deployment.json`. A26 completed the identity diagnosis and
retained its rule safeguard as an unapplied candidate; see
[the review decision](../A26-person-context/DECISION.md).
