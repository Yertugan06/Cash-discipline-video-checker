# Your assignment: the door rule (A-DOOR-LOCK), worktree branch orch/door

Targets (baseline A17):
- Х-29 (clean) is flagged A-DOOR-LOCK at 0.0 s. A finding at the very first frame usually means a
  state read before anything happened, not an observed violation.
- Х-32 (violation, organizer second 5): the cashier walks in (3-5 s) and leaves the booth door open.
  Missed.
- Х-33 (violation, organizer second 6): the cashier enters (2-5 s) and doesn't close the door
  (6 s); an outsider enters at 10-14 s. Missed. A-OUTSIDER-ZONE may also be relevant here.
- Х-30 (violation, caught by A-OUTSIDER-ZONE at 13 s) and Х-46 (violation, A-DOOR-LOCK at 0.0
  among others) must stay caught.

Find out from the cached door states (CLIP open/closed per frame, scores and margins), the door
zone and the people tracks why the rule fires on Х-29 and stays silent on Х-32/Х-33. Then fix the
mechanism. The norm: a cash booth door must be closed/locked while the cashier works in it
(НБРК № 14, п. 16). Check every clean clip for door findings after your change.
