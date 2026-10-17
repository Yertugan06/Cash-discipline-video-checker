# A12 - ADR-002 service with the F1 detector (live)

- **Date:** 2026-10-17, deployed 15:45 UTC, evidence boxes added ~16:00 UTC
- **Status:** live on `datathon`; **not evaluated on the 40 videos yet**
- **Where it runs:** `datathon:~/datathon26`, compose project `datathon26`
  (`docker compose -p datathon26 -f compose.yaml -f compose.gpu.yaml`), container
  `datathon26-checker-1`, `127.0.0.1:8000` only. Code = commit `69662c2` plus the uncommitted
  evidence-box change (`~/datathon26/DEPLOYED_COMMIT`).
- **Models:** as A01 - RT-DETR r18vd, OWLv2 base-patch16-ensemble, CLIP ViT-B-32 laion2B,
  RTMPose-m wholebody ONNX, ByteTrack. No VLM (`DETECTOR=f1`).

## Approach

A01's F1 stack behind the ADR-002 service: jury API, 270 s job deadline, 2 fps sampling,
findings filtered to the canonical rules in `knowledge/rules.yaml`, ranked (top 3), grounded to
norms (all `needs_review`), evidence frames from the source video. New in this attempt: the
box of the object that triggered a finding is drawn on its anchor evidence frame
(`backend/evidence.py`, `Finding.boxes` in `backend/contracts.py`).

## Results so far

| Check | Result |
|---|---|
| `/healthz`, `/readyz` | 200 |
| Test suite (in the app image on the VM) | 174 passed, 2 skipped, 2 failed (both failing before this change: `test_api.py::test_health_and_ready_need_no_key`, `test_pipeline.py::test_pipeline_runs_against_wp3s_real_knowledge_and_rank`) |
| X-1 smoke test via `scripts/jury_client.py` | done in 50.8 s cold, 4.1 s with perception cache; contract-valid; verdict `violation`, 1 finding |
| Full 40-video eval | not run |

### X-1 trace

The only finding is W-NO-PERSONAL-ITEMS at 20.0 s. The verdict matches the label, but the
evidence is weak:

- OWLv2's `"a handbag"` prompt matched a static box (x 0.07-0.27, y 0.50-0.58) at scores
  0.22-0.32, with the threshold at 0.12. The same box shows up at 0.0 s and 1.5 s, so it's
  probably a fixed object, not a bag that was put down.
- Between 2 and 16 s the score dropped below 0.12 and the track disappeared.
- 16.5-19.5 s lasted exactly 3.0 s, but the rule needs more than 3.0 s.
- At 19.5 s the interval broke (probably a wrist within 0.07 counted as "carried"). It
  restarted at 20.0 s and ran 6.0 s, which became the finding. So 20.0 s is a restart
  artefact, not the moment an object was placed.
- A `tablet:56` box sits next to it at the desk edge (x 0.00-0.08), so this corner seems to
  hold something the detector keeps relabelling.

## Live verdict gateway (2026-10-17 ~16:35 UTC)

`realtime/` (separate from `backend/`) runs as container `datathon26-realtime` on
`127.0.0.1:8100` and streams verdicts over a WebSocket. A full run of the 42 files in
`~/data/open/videos` (40 unique clips plus duplicates) was started through it, one job at a
time. First results: X-1 violation (= label), X-2 violation (= label), Х-3 violation (label:
no violation). Results are persisted on the VM in `~/realtime-state/state.json`; the full-run numbers still need to
be copied here from `/api/state` when the run ends.

## Logs

- `logs/x1/replay.txt` - cached-perception replay: scene objects, every coat/handbag
  detection, people at 19-26 s, PERSONAL_ON_DESK events, all findings
- `logs/x1/evidence_W-NO-PERSONAL-ITEMS_20.0s.jpg` - the evidence frame the API returns, with the trigger box
- `logs/x1/all_detections_20.0s.jpg` - every detection and scene object at 20.0 s
- `scripts/debug_x1.py`, `scripts/overlay_x1.py` - run inside the container
  (`docker cp` then `docker exec datathon26-checker-1 python /tmp/<script>`)

## Next

1. Run all 40 videos through the API and score with `eval/run_eval.py`.
2. Fix the static-object false positive: treat objects already present at calibration as
   furniture, raise the handbag threshold, timecode from first stable appearance.
3. Tighten A01's false-alarm rules (A-OUTSIDER-ZONE, A-SECOND-PERSON, L-NO-DOCS-ON-LEAVE).
