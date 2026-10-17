# Your assignment: client-session rules, worktree branch orch/sessions

Rules: C-ID-BEFORE-CASH, A-SECOND-PERSON, S-CLEAN-DESK-HANDOVER, C-COUNT-BEFORE-EXIT (see
backend/f1/rules.py and config/f1_codex.yaml), plus the session tracking in events.py they use.

Targets (baseline A17, all missed violations):
- X-2 (second 10): the client comes in (4-8 s), sits down and puts blue banknotes down at once;
  cash accepted without identifying the client (no ID card shown).
- Х-18 (second 20): client 1 is being served (money on the desk); at 17-18 s a second client comes
  in. Two clients served at once.
- Х-38 (second 33): client 1 is served and leaves (~24 s); a stack of blue banknotes stays on the
  desk while the next client is served. The previous client's money wasn't put away.
- Х-34 (second 13): the client puts money down (7-8 s), sits, but at 11-14 s gets up and leaves
  while the cashier counts. Counting not in the client's presence.
- Х-4 (violation, caught by C-ID-BEFORE-CASH at 66 s) must stay caught.

Read the full row for each clip in the team spreadsheet. For each target, check whether the cached
perception sees the needed facts: the people, their roles and sides, entries and exits, cash or
ID-card boxes. Then decide whether a rule can fire on that signal without firing on the clean
clips that have clients (check every clean clip for findings of these rules after your change).
Expect that cash and ID cards are poorly detected (A13: cash seen in 4 of 11 frames). For clips
where the signal isn't there, say so with numbers.
