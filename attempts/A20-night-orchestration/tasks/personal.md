# Your assignment: personal items (W-NO-PERSONAL-ITEMS), worktree branch orch/personal

Targets (baseline A17):
- Clean clips flagged W-NO-PERSONAL-ITEMS: Х-14 (0.0, 19.0, 34.0, 39.5 s), Х-35 (0.0 s),
  Х-48 (28.0 s).
- Х-40 (violation, organizer second 17): the cashier comes in wearing outerwear with a bag and at
  13-17 s puts personal things on the desk. Missed.
- These violation clips are currently caught *only or partly* through W-NO-PERSONAL-ITEMS and
  must stay caught (check what each one's real violation is in the team spreadsheet, since some of
  these hits may be lucky): X-1, Х-4, Х-11, Х-13, Х-15. Use $S/base.txt.

Find out what object labels, positions, times and track lifetimes make the rule fire on the clean
clips and the violation clips. Look especially at findings at 0.0 s (an object on the desk from
the first frame), objects that are fixtures or the cashier's work tools, and the detector's
prompts in config/perception.yaml. The norm (НБРК № 231, п. 12 ч. 1): personal belongings and
personal money must not be kept at the cashier's workplace. Be careful: if the only way to
remove the clean false alarms also removes lucky hits on violation clips whose real violation is
something else, report that trade-off honestly with numbers rather than hiding it.
