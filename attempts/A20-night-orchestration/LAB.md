# LAB - the search for the best solution (A20, started 2026-10-18 night)

The shared working file for the experiment phase, for the team, the orchestrating agent, Codex
agents, and outside reviewers (GPT Pro, Claude). Anyone resuming should read this first and keep
it updated. While experiments run, **the main docs (README, docs/ARCHITECTURE_SUMMARY.md,
CONTEXT.md, STATUS.md) are not updated**; results live here and in `attempts/`.

## 1. Goal and constraints

- **The service:** a bank cashier CCTV clip in, then "violation" or "no violation", plus each
  violation's type, timecode, evidence frame, description and legal norm (Kazakhstan National Bank
  rules).
- **Jury scoring (100 points):**

  | Criterion | Points |
  |---|---|
  | Verdict | 25 |
  | Timecode and evidence frame | 15 |
  | Violation type | 15 |
  | Legal grounding | 15 |
  | Robustness on unseen videos and camera angles | 10 |
  | Product | 10 |
  | Architecture | 10 |

  The jury tests on new videos through the API.
- **Hard limits:**
  - Local only, no cloud AI while processing videos.
  - One NVIDIA L4.
  - At most 300 s per video; we budget 270 s.
  - Offline after the weights are downloaded.
  - No cloud AI tools on dataset videos or frames. Text, numbers and scores are fine.
- **Data:** 40 unique labelled clips (21 violation, 19 clean; many clean clips are twins of a
  violation clip). The organizer gives a verdict and a second for each. The team's descriptions are
  in `data/Таблица_нарушений.xlsx`. There's no box ground truth.
- **Target:** maximise the verdict accuracy on the 40 clips **without** fitting them. A change has
  to be a mechanism that makes sense on unseen clips and camera angles. Secondary targets:
  timecode error, the right violation type, and robustness under the perturbation probes (section 6).

## 2. The system being improved (F1 stack, `backend/f1/`)

Pretrained detectors only describe each frame. Deterministic temporal rules decide.

1. ffmpeg samples frames at 2 fps.
2. Perception (`perception.py`):
   - RT-DETR finds people; ByteTrack tracks them.
   - OWLv2 finds scene objects (desk, safe, door, laptop, money counter) and small objects in a desk
     crop (cash, bundle, bag, ID card, document, tablet, cup, food, phone, handbag, coat).
   - OpenCLIP gives states: safe/door open or closed, laptop working or locked, counter running or idle.
   - RTMPose gives hand keypoints.
3. Calibration (`calibration.py`) sets up the zones and the cashier/client sides.
4. The event builder (`events.py`) turns this into events: enter/exit with roles, workstation away,
   items, states, counting, handovers, client sessions.
5. Rules (`rules.py`, thresholds in `config/f1_codex.yaml`) produce findings. Only rule ids enabled
   in `knowledge/rules.yaml` count.

## 3. Scoreboard (offline replay, 40 clips, organizer labels)

| Version | Correct /40 | Clean false alarms /19 | Missed /21 | Drop-0.2 mean correct (3 seeds) |
|---|---|---|---|---|
| Always "violation" (floor) | 21 | 19 | 0 | - |
| A17 (live on the VM, `main`) | 25 | 5 | 10 | - |
| night + door | 26 | 4 | 10 | 25.3 |
| night + personal gaps | 27 | 4 | 9 | - |
| night + sessions | 30 | 4 | 6 | 28.7 |
| night + leave persistence | 31 | 3 | 6 | 29.7 |
| night + counter is not a personal item (honest; 4 lucky catches lost) | 28 | 2 | 10 | - |
| night + a cash bag counts for cash-on-leave | 29 | 2 | 9 | - |
| **night + fp: hand on equipment = still at the desk; worn-coat fragments (current)** | **31** | **0** | **9** | **30.7** |

Timecodes of the current version (`replay_f1.py timing`): 12 caught violations, mean |offset| to
the organizer second 1.46 s (was 1.83 s), within ±1/2/3/5 s: 7/9/10/12.

Robustness of the current version (after the scale fix): zoom 0.7 / 0.8 / 1.2 / 1.3 and mirror all
give exactly 31/0/9; dropping 20% of object detections gives 30-31 / 0 / 9-10 (3 seeds); 30% gives
30/0/10; zoom 0.8 + drop 0.2 + mirror at once gives 30/0/10.

Earlier approaches (VLM questionnaire, video VLM, embeddings, desk-object tracking, ...) all scored
20-23, see `attempts/README.md`.

## 4. Decision log

| When | Decision | Why |
|---|---|---|
| 10-18 | The desk-object tracking idea (A18/A19) is rejected; desk change survives as an item finder | Naming items from history clues failed: the clues weren't independent, and the detector rarely overlaps the blobs |
| 10-18 | Work as an orchestrator plus Codex agents: one rule family per agent, each in its own git worktree branch `orch/<name>` from `night` | Parallel work; the orchestrator re-runs everything and merges only verified gains |
| 10-18 | No per-clip hacks, and no thresholds fitted to flip single clips; every change needs a unit test; a "fix 2, break 2" change is rejected | The jury scores unseen videos |
| 10-18 | Robustness probes added to the replay: `--mirror`, `--zoom`, `--drop`, `--seed` | A cheap stand-in for other cameras or a weaker detector, with no GPU or video needed |
| 10-18 | KEPT, door: an "entry" at the first frame isn't an observed entry | Removed a clean false alarm on Х-29 |
| 10-18 | KEPT, personal items: bridge brief detection gaps within one track | Caught Х-40; more robust to dropped detections |
| 10-18 | **The money counter must not count as a personal item, even if it costs catches.** Recover those clips through their real violation | OWLv2's "handbag" prompt matches the counter (IoU 0.7-0.98); most personal-item catches were wrong-type luck |
| 10-18 | KEPT, sessions: client re-identification, client exit only after moving away from the desk, a sustained second client at the desk, the counter still running when the client leaves | Caught Х-18, Х-34 and Х-38 with timecodes within 0.5-2 s |
| 10-18 | KEPT, leave: an item counts only if seen in at least 2 frames of each short evidence window, and the cashier is gone for the whole confirmation delay | Fixed Х-8 (a 1 s step-away); leave catches now survive dropped detections |
| 10-18 | KEPT, counter: boxes matching the calibrated laptop/counter or repeated equipment candidates are not personal items | The user's decision; Х-48 fixed; lost lucky X-1, Х-11, Х-13, Х-15 |
| 10-18 | KEPT, `L-NO-CASH-ON-LEAVE` checks cash bags too, as its Knowledge Pack mechanism already says | Recovered Х-15 by its real violation, at the organizer's exact second |
| 10-18 | KEPT, fp: a confident hand inside the laptop/counter box means the cashier is still at the workstation; a small coat box above the person's hip line is worn clothing | Cleared the last clean false alarms (Х-14, Х-35); Х-40's coat on the desk stays caught |
| 10-18 | REJECTED for now: replacing the CLIP door/screen states with new CLIP prompts or Qwen2.5-VL-7B | Spike (`spikes/states_spike.py`, `logs/states.jsonl`): both answer "open" for the door almost always, and Qwen calls lock screens "working" (laptop 10/32) |
| 10-18 | LEAD, not built: "did the screen change since the cashier last worked at it?" instead of naming the screen state | Probe (`spikes/screen_probe.py`, `logs/screen.jsonl`): a naive before/after-leave window doesn't separate the clips (the lock happens before standing up; a light switched off in Х-11). Needs the last hands-on-laptop moment as the reference; only 2 violation vs 4 clean clips to judge on |
| 10-18 | KEPT, timecode: `replay_f1.py timing` scorer; ranking prefers a finding with a confirmed exit among equals; `K-SEAL-CHECK` anchors at the collector's exit | Better top-1 timecodes, no verdict change |
| 10-18 | KEPT, scale: scene distances are multiples of the calibrated desk length (`× desk_long_side / 0.70`) instead of fixed image fractions | Another camera distance (zoom 0.7-1.3) no longer changes any finding |
| 10-18 | Main docs frozen during experiments | Decided by the user |

## 5. Findings (facts measured in the cache)

- **Small objects are poorly detected:** cash was seen in 4 of 11 hand-labelled frames (A13).
  Keys, seals and the authenticity detector are essentially never seen. X-2 has cash and ID cards
  in 0 of 34 frames.
- **Most early false alarms were findings at second 0**, from objects or states already there when
  the clip starts.
- **The money counter shows up as "handbag"** (IoU 0.70-0.98 on Х-11, Х-13, Х-14, Х-15). Some clips
  have no calibrated counter at all (X-1, Х-4/Х-47).
- **CLIP states are unreliable for some scenes:** the laptop reads "closed" in all 51 frames of
  Х-11 (and of clean Х-12). On Х-32 the door reads closed at the organizer's second (score 0.76).
- **"handbag" also matches the laptop** in clips without a calibrated counter (X-1, Х-4, Х-48).
- **Robustness:** mirroring changes nothing; zoom ±20% moves the result by 1-2 clips; dropping 20%
  of object detections costs about 1-3 clips (the current version is more robust than A17).
- **Cache trap:** each clip's cache folder holds 4 versions, and the replay takes the newest by
  file time. Copy it with `cp -a` or `tar`, never `cp -r`, or the results change.

## 6. Task board

| Task | Status | Owner / branch |
|---|---|---|
| door: Х-29 false alarm, Х-32/Х-33 missed | merged (Х-29 fixed; Х-32/Х-33 need better door perception) | `orch/door` |
| personal: Х-14/Х-35/Х-48 false alarms, Х-40 missed | merged (Х-40 fixed) | `orch/personal` |
| sessions: X-2, Х-18, Х-34, Х-38 missed | merged (3 of 4; X-2 has no cash/ID signal) | `orch/sessions` |
| leave: Х-8 false alarm + leave-rule robustness under drop + timecodes | merged | `orch/leave` |
| counter: counter is not a personal item; Х-13; signal report | merged (Х-13: no recount/safe signal in the cache) | `orch/counter` |
| Recover the lucky clips by their real violations | Х-15 done (cash bag); Х-11 needs screen-state perception; X-1, Х-13, Х-4 have no signal in the cache | orchestrator |
| fp: clean false alarms Х-14 (leave at 62.5 s), Х-35 (worn-coat fragment) | merged (both fixed) | `orch/fp` |
| scale: distances relative to a scene scale so --zoom 0.8/1.2 keeps the result | merged (every zoom 0.7-1.3 = 31/0/9) | `orch/scale` |
| Teammate's `local-vlm-prototype` (Qwen3-VL 4B questionnaire + D-FINE + 8B action windows; self-reported 32/40, 3/19 clean FP): run it on the VM on the same 40 clips and compare per clip; then a combination | running | orchestrator |
| timecode: timing scorer + explainable anchor fixes, no verdict change | merged (no verdict change; ranking prefers a confirmed exit) | `orch/timecode` |
| End-to-end check: run `night` through the real API in a second container (port 8001, same perception cache), the 40 clips: runtime, evidence frames, serializer | next | orchestrator |
| Perception: door and laptop-screen states are misread by CLIP (Х-32/Х-33 door, Х-11 screen) | spike done: new prompts and Qwen 7B don't fix it; "screen changed?" is a lead | orchestrator |
| Threshold search with cross-validation over twin groups (report the held-out score) | idea | - |
| Х-17 (seal check), Х-22 (key in lock), Х-44 (authenticity detector) | idea, probably a perception limit | - |
| Timecode pass: rule anchor vs organizer second | idea | - |
| Remaining clean false alarms: Х-14, Х-35, Х-48 (personal), Х-8 (docs) | partly in leave/counter | - |

**Still failing on night:** missed X-1, X-2, Х-11, Х-13, Х-17, Х-22, Х-32, Х-33, Х-44; no clean
false alarms. The per-clip list is in `logs/night7.txt`. Every miss is a perception limit: no cash,
ID, key, seal or authenticity-device signal (X-1, X-2, Х-13, Х-17, Х-22, Х-44), or unreadable
door/screen states (Х-11, Х-32, Х-33).

## 7. How to resume (any session or tool)

```bash
LAB=~/projects/hackathons/dt26-lab        # perception cache (numbers only) + Python env + run logs
cd ~/projects/hackathons/dt26-wt/night    # integration branch `night` (git worktree of the repo)
export API_KEY=x PYTHONPATH=.
$LAB/venv/bin/python scripts/replay_f1.py run --cache-dir $LAB/perception_cache > /tmp/r.jsonl
$LAB/venv/bin/python scripts/replay_f1.py score /tmp/r.jsonl --labels data/prepared/videos.jsonl
# robustness: add --drop 0.2 --seed 0|1|2, --zoom 0.8, --mirror
$LAB/venv/bin/python -m pytest -q tests/test_f1_rules.py tests/test_f1_detector.py tests/test_desk_objects.py
```

- **Branches:** `night` is the integration branch, and each agent works on `orch/<task>`. Worktrees
  are in `~/projects/hackathons/dt26-wt/<task>`. Agent reports are in `reports/` here.
- **Start a Codex agent:** run `codex exec -C <worktree> -s workspace-write --add-dir $LAB --add-dir
  <repo>/.git -o report.md "<brief>"`. The brief is the "Shared brief" (rules for agents: no
  frames, no per-clip hacks, tests, a report format) plus one task.
- **The live service on the VM** still runs A17 (`main`). Nothing from `night` is deployed yet.
- **Merge rule:** re-run the replay and the drop seeds yourself, and keep a change only if
  full-data correct doesn't fall and no clip breaks without a stated reason.

## 8. Questions for outside reviewers (GPT Pro, Claude)

1. Which perception upgrade would most help small objects (cash, documents, keys, seals) within
   the budget? SAM 2, a better open-vocabulary detector, a tiny classifier on hand-labelled crops,
   higher fps on the desk crop, or a VLM only at the moments the rules flag?
2. How do we get independent evidence that "this object is cash" from hands and motion
   (counting, fanning, passing it across the desk)?
3. Would a probabilistic or HMM state model beat hard thresholds here, and how would we validate
   that on 40 clips without fooling ourselves?
4. Which violation types should we drop as not visually checkable, to protect precision?
5. What's the best use of the clean/violation twin structure?
6. What are we missing?

Answer as a ranked list: what to build, why it fits, the expected effect on misses and false
alarms, the cost in hours, and a quick check.
