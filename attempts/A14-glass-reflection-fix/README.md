# A14 - Glass reflections, desk calibration and the cashier/client split (F1, live)

- **Date / who:** 2026-10-17, agent session
- **Status:** live on `datathon` (run 3 config); follow-up idea (VLM roles) not started
- **Where it ran:** `datathon`, checker `datathon26-checker-1` (`DETECTOR=f1`), gateway
  `datathon26-realtime`. Code = `5e618b8` + uncommitted changes (`~/datathon26/DEPLOYED_COMMIT`).
- **Models:** as A12 (RT-DETR r18vd, OWLv2, CLIP, RTMPose-m, ByteTrack). No VLM.

## Why

In A12's live run `A-OUTSIDER-ZONE` fired on about 25 of 42 clips, 10 of them clean. Only Х-30
and Х-33 have a real outsider (`data/prepared/events.jsonl`). The perception cache, replayed
through `build_events` (`logs/before_role_events.txt`, `logs/before_person_tracks.txt`), showed:

1. Reflections and people behind the glass wall get person boxes (left pane, box bottom 0.30-0.39).
2. The desk prompt often matched a desk seen through the glass (`[0.30,0.08,0.49,0.11]`) or the
   side desk, which put almost the whole frame on the cashier side.
3. Х-3: a 3%-tall phantom "person" on the laptop won the cashier role, so the real cashier,
   alone in the room, became `outsider`.
4. The cashier/client split (desk centre -> laptop) runs sideways when the laptop is at a desk end.

## Changes

- `person_min_height: 0.05` (`config/perception.yaml`, applied in `perception.people`).
- Desk = the desk the laptop stands on (`calibration.calibrate`); raw candidates kept on `Scene`.
- Person boxes ending above the desk's far edge minus `glass_margin` get role `glass` and are
  ignored (`events.EventBuilder.push`).
- Run 3: cashier side = near (lower) side of the desk. Assumes the camera looks over the
  cashier's shoulder.
- Diagnostics: per-job trace `/app/runtime/traces/<job_id>.json`, a log line per stage, replay
  player with an Objects toggle, `/compare` page, `scripts/replay_f1.py`.

## How to reproduce

```
POST http://127.0.0.1:8100/api/run-folder      # on datathon, gateway
docker run --rm --entrypoint '' -v datathon26_work:/app/runtime:ro -v $PWD:/work:ro -w /work \
  -e PYTHONPATH=/work -e API_KEY=x forte-cash-checker:cuda python scripts/replay_f1.py run > r.jsonl
python scripts/replay_f1.py score r.jsonl --labels data/prepared/videos.jsonl
```

## Results

Live runs, 42 files (40 unique clips + duplicates), gateway scoring against labels.
Saved on the VM as `~/realtime-state/state.<run>.json`, visible side by side on `/compare`.

| Run | Match label | Clean false alarms | Missed | Outsider on clean | Worst runtime |
|---|---|---|---|---|---|
| before-glass-fix (A12 code) | 25/42 | 12/20 | 5/22 | 10 | - |
| run2-sideways (fixes 1-3, desk->laptop split) | 19/42 | 15/20 | 8/22 | 2 | - |
| run3-nearfar (fixes 1-3, near/far split) | 23/42 | **6/20** | 13/22 | **0** | 146.6 s |

Offline replay on the same 40 cached clips: sideways 18/40 (14 clean FP, 8 missed), near/far
22/40 (5 clean FP, 13 missed), learned side from "person nearest the laptop" 21/40 (13 clean FP,
6 missed).

- Run 2 got worse because, once the cashier role and the real desk were found, the sideways
  split often put the seated cashier "away", so `L-NO-DOCS-ON-LEAVE` fired on clean clips.
- The learned split fails when the laptop is at a desk end: the client behind the desk is as
  close to the laptop as the cashier (`logs/learned_split_anchors.txt`).
- Х-30 is caught by the learned split (outsider at 13.0 s) but not by near/far.

## Logs

- `logs/live_run1_before.txt`, `logs/live_run2_sideways.txt`, `logs/live_run3_nearfar.txt`
- `logs/replay_*_split.txt` / `.jsonl` - offline replays and per-video findings
- `logs/before_role_events.txt`, `logs/before_person_tracks.txt` - the diagnosis
- VM: traces in volume `datathon26_work` (`/app/runtime/traces/`), states in `~/realtime-state/`

## Conclusion

- Outsider false alarms on clean clips went from 10 to 0, and clean false alarms from 12/20 to
  6/20. The cost is misses (5 -> 13): many "correct" violation verdicts were lucky outsider hits
  or came from the leave rules.
- Remaining clean false alarms are static objects at t=0 (`W-NO-PERSONAL-ITEMS@0.0`),
  `A-DOOR-LOCK` and `A-SECOND-PERSON`, not glass.
- Near/far depends on the camera angle (Х-14 may be a camera facing the cashier). Proposed next:
  roles and situation (client service / cash collection / walk-through) from a local VLM
  (Qwen2.5-VL-7B, Apache-2.0) on a few person-marked keyframes, with rules staying
  deterministic. A spike on about 10 clips comes first.
