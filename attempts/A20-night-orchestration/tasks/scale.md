# Your assignment: scale invariance (another camera distance), branch orch/scale (from night)

Baseline (night): full data {"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9}
(per clip: /home/sultanbek/projects/hackathons/dt26-lab/runs/night7.txt). The replay probe `--zoom Z` rescales every cached coordinate about
the image centre (Z < 1: the camera is farther away, the scene is smaller in the frame):
--zoom 0.8 -> 28 / 1 / 11, --zoom 1.2 -> 29 / 0 / 11 (/home/sultanbek/projects/hackathons/dt26-lab/runs/n7z0.8.jsonl, n7z1.2.jsonl).
Mirror and --drop 0.2 are already stable.

The cause is probably distances in normalised image units that don't scale with the scene:
hand_distance (config/perception.yaml), LAPTOP_REACH, LAPTOP_HAND_MARGIN, glass_margin, the
0.045 wrist distance in Context.on_desk, the boundary/border margins for entries and exits,
person_min_height, desk_distance margins, the 0.12/0.18 frame-border tests and others.
Find which ones flip which clips under zoom (diff the per-clip output), then express them relative
to a scale measured in the scene itself (e.g. the calibrated desk or laptop width, or the median
cashier box height). Choose the reference so the full-data result stays exactly the same (the
constant becomes "k x reference", with k chosen so k x reference equals today's value on a
typical clip, not tuned per clip).

Note: zoom about the image centre also pushes things off-frame at Z > 1 and changes the distance
to the frame border, so border-based entry/exit tests may legitimately change. Separate those from
the scale bugs and explain them.

Goal: full data unchanged at 31/0/9 (or better); --zoom 0.8, 0.9, 1.1, 1.2 as close to it as
possible; --drop 0.2 seeds 0/1/2 not worse (30/31/31) and --mirror unchanged. Report all lines.
