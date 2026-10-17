# Your assignment: leave rules and robustness to detection loss, branch orch/leave (from night)

Your branch starts from `night` (A17 + a door fix). Its baseline:
{"videos": 40, "correct": 26, "clean_false_alarm": 4, "missed": 10}; per clip: /home/sultanbek/projects/hackathons/dt26-lab/runs/night.txt.
Rules: L-NO-CASH-ON-LEAVE, L-NO-DOCS-ON-LEAVE, L-NO-BAG-ON-LEAVE, L-PC-LOCKED, L-SAFE-LOCKED-ON-LEAVE
(rules.left_with, Context.leaves, Context.on_desk, and the leave/away events in events.py).
Read attempts/A17-leave-rule-fixes/README.md and attempts/A18-desk-object-history/README.md first.

Targets:
1. Х-8 (clean) is flagged L-NO-DOCS-ON-LEAVE at 9.5 s: a "document" lies in the desk corner from
   the first frame. Find the general reason it counts as "left behind".
2. Robustness: `scripts/replay_f1.py run ... --drop 0.2 --seed N` replays the clips with 20% of
   non-person detections randomly lost (a weaker detector or another camera). On night, with
   seeds 0/1/2, the leave-rule catches Х-26 (L-NO-CASH-ON-LEAVE, organizer 9 s) and Х-20
   (L-NO-DOCS-ON-LEAVE, organizer 5 s) are lost in some seeds (/home/sultanbek/projects/hackathons/dt26-lab/runs/nd0.txt, nd1.txt, nd2.txt).
   Make the leave rules depend on persistent evidence over a short window (e.g. "seen in k of the
   n frames around the moment") instead of one exact frame. They should still catch on full data
   and not start firing on clean clips.
3. Timecodes: for each leave-rule hit, compare the finding time with the organizer second and
   report the offset. Fix it only if there's a systematic, explainable offset.

Measure on the full data and on --drop 0.2 with seeds 0, 1, 2 (report all 4 score lines and the
mean). The goal: the full-data score is no worse than 26/4/10, and the mean under drop goes up.
