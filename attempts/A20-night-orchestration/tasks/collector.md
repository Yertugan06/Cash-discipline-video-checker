# Your assignment: collector leaves right after the handover (K-SEAL-CHECK), branch orch/collector (from night)

Baseline (night): {"videos": 40, "correct": 31, "clean_false_alarm": 0, "missed": 9}; per clip:
/home/sultanbek/projects/hackathons/dt26-lab/runs/night9.txt. Read attempts/A20-night-orchestration/LAB.md first.

The team's description of the twin pair (text, from the user):
- Х-17 (violation, organizer 7 s; camera behind the cashier): a man comes in with a bag, passes the
  bag across the desk, the cashier takes it, and the man **leaves straight away**, closing the door.
  The bag is accepted without checking its seal while the collector is present.
- Х-16 (clean twin, same camera): a man comes in with a bag and closes the door, stands in front of
  the cashier, shows his ID card (she checks both sides and gives it back), hands over the bag and
  **sits down at the desk** (he stays).

An earlier report says the cache has the bag in 7/29 observations of Х-17 and zero bag-handover
events, so don't rely on a handover event. Look at what F1 does see: person tracks (entry, exit,
how long a visitor stays, standing or seated, whether they came close to the desk), bag detections
anywhere in the frame, and where the bag is after the visitor leaves.

Goal: K-SEAL-CHECK (or the rule its codex entry describes) fires on Х-17 near 7 s because a
visitor who brought or handed over a bag left within a short time without staying, and it does
not fire on Х-16 or any clean clip. It must be a general mechanism (visit pattern + bag evidence),
scale-relative like the rest of night (see backend/f1 for the desk-scale helpers), and robust:
report full data, --drop 0.2 seeds 0/1/2, --zoom 0.8/1.2 and --mirror. The current night results
for those probes are all 31/0/9 (drop: 30-31). If the cache simply can't separate Х-17 from Х-16,
say so with numbers.
