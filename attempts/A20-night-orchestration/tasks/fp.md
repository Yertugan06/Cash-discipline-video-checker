# Your assignment: the last clean false alarms, branch orch/fp (from night)

Baseline (night): {"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9}; per clip:
/home/sultanbek/projects/hackathons/dt26-lab/runs/night6.txt. Read attempts/A20-night-orchestration/LAB.md and reports/leave.md,
reports/personal.md and reports/counter.md first: earlier agents already examined these clips.

Targets:
1. Х-14 (clean) is flagged L-NO-CASH-ON-LEAVE and L-NO-DOCS-ON-LEAVE at 62.5 s. Find out what
   the "leave" at 62.5 s really is in the cached data (does the cashier leave the room, step
   away briefly, stand up in place?) and what the "cash"/"document" on the desk is (a fixture?
   the counter? the laptop? something the cashier is working with?). The team sheet's "Без
   нарушений" row for Х-14 says what really happens.
2. Х-35 (clean) is flagged W-NO-PERSONAL-ITEMS at 0.0 s: a narrow "coat" box mostly inside a
   person box (a coat the person is wearing). An earlier broader worn-coat filter also suppressed
   Х-40's real coat on the desk (organizer 17 s), which must stay caught.

Every currently caught violation must stay caught on full data. Report the drop-0.2 seeds 0/1/2.
