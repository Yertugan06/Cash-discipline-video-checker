# A20 - Night orchestration: verified rule fixes on F1, robustness probes, teammate merge

- **Date / who:** 2026-10-18 (night), orchestrating agent + Codex agents, decisions by the user
- **Status:** measured; merged to `main` together with the `fix-dataset` branch
- **Where it ran:** offline replay on the cached perception of the 40 unique open videos (laptop,
  no GPU); end-to-end API check on `datathon` (test container on port 8001, `RULE_SCOPE=detector`)
- **Models:** as A14-A17 (RT-DETR, OWLv2, OpenCLIP, RTMPose, ByteTrack); no new model in the
  merged code

## Approach

One agent orchestrated, and Codex agents each fixed one rule family in its own git worktree. The
orchestrator re-ran every branch, compared it clip by clip and merged only verified gains. The
rules for every change: no per-clip special cases, no thresholds fitted to flip single clips, a
unit test that fails without the change, and no clip broken without a stated reason. The full
working log is `LAB.md` (scoreboard, decision log, findings, task board, how to resume).

What changed in the event builder and rules is summarised in `docs/ARCHITECTURE_SUMMARY.md`
("What the rules rely on"). The agents' reports are in `reports/`, their briefs in `tasks/`,
the team's description of every clip in `clip-descriptions.md`.

New evaluation tools:
- `scripts/replay_f1.py run --mirror | --zoom Z | --drop P --seed N`: replay the clips as another
  camera or a weaker detector would report them (robustness without new videos or the GPU).
- `scripts/replay_f1.py timing`: each caught violation's anchor vs the organizer second.
- `spikes/api_run.py`: run a folder of videos through a checker API and save each result.

## How to reproduce

See `LAB.md` section 7. In short, with the perception cache copied by `tar` or `cp -a` (each
clip folder holds several cache versions and the replay picks the newest by file time):

```
export API_KEY=x PYTHONPATH=.
python scripts/replay_f1.py run --cache-dir <perception_cache> > r.jsonl
python scripts/replay_f1.py score r.jsonl --labels data/prepared/videos.jsonl
python scripts/replay_f1.py timing r.jsonl --labels data/prepared/videos.jsonl
```

## Results

Offline replay, 40 unique videos, organizer labels:

| Version | Correct /40 | Clean flagged /19 | Missed /21 |
|---|---|---|---|
| A17 (start of the night) | 25 | 5 | 10 |
| **A20 (merged)** | **32** | **0** | **8** |
| teammate `local-vlm-prototype` v3, measured the same way | 32 | 1 | 7 |

- Robustness (A20): `--zoom 0.7 / 0.8 / 1.2 / 1.3` and `--mirror` give exactly 32/0/8;
  `--drop 0.2` (3 seeds) 31-32 / 0 / 8-9.
- Timecodes (A20): 13 caught violations, mean |offset| 1.54 s; within ±1/2/3/5 s: 7/9/11/13.
- End-to-end through the real API (the merged code in a test container on `datathon`,
  `RULE_SCOPE=detector`, all 42 files through a second realtime gateway): **32/40, 0/19, 8/21,
  the same verdicts as the replay**, no failed job, wall time median 20 s and worst 89 s with the
  perception cache (`logs/api-gateway-final.jsonl`). The team's `eval/check_outputs.py` on the 24
  dev clips (lockbox skipped by design): TP 9, FN 3, FP 0, TN 12, every response valid against the
  jury schema, none over 300 s, best finding within ±3 s on 8/9 (`logs/check_outputs-dev.txt`).

## Logs

- `LAB.md` - the working file; `logs/` - per-clip replays, API runs, spikes; `reports/` - agent
  reports; `tasks/` - agent briefs; `spikes/` - the GPU spikes (door/screen states, screen change)
- [Main integration and annotation audit](reports/main-integration-and-annotation-audit.md):
  local annotation/run-browser integration, 761 passing Python tests, a fresh cached replay
  matching the API verdicts/rule IDs, and all 40 unique outputs compared with human descriptions.
  It separates label agreement from supported explanations and preserves clip-boundary uncertainty.
- [Claude Opus 5.5 tracking review](reports/opus-5-5-small-object-review.md): user-approved
  high-effort text review of the small-object proposal, checked against the code. Recommends a
  native-crop/sequence diagnostic before additional tracking; no new performance result is claimed.
- [Claude Opus 5.5 ID-rule review](reports/opus-5-5-id-rule-review.md): separately approved
  high-effort review after the X-19 correction. Preserves observed events and organizer labels
  while keeping the blanket visual requirement provisional; no runtime or label changes.
- [Next cash-workflow experiment](reports/next-cash-workflow-experiment.md): prepared recognition
  comparison using existing labels, followed conditionally by client cash-history checks and a
  full regression. Planning only; no new experiment result or detector change.

## Conclusion

Rule-level fixes took F1 from 25 to 32 of 40 with no clean video flagged, stable under camera
distance, mirroring and detection loss. The 8 misses left are perception limits: cash, ID cards,
keys, seals and the banknote detector are not seen (X-1, X-2, Х-13, Х-22, Х-44), and the door,
laptop screen and safe states can't be read by CLIP (Х-11, Х-32, Х-33). A spike showed new CLIP
prompts and Qwen2.5-VL-7B don't read them either; the teammate's Qwen3-VL 4B crop questions do on
these clips, which is the next step (VLM checks at F1's own event moments, not merged yet).
