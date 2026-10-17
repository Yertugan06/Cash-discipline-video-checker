# Your assignment: the money counter is not a personal item, branch orch/counter (from night)

Your branch starts from `night` (A17 + door fix + personal-item gap bridging). Baseline:
{"videos": 40, "correct": 27, "clean_false_alarm": 4, "missed": 9}; per clip: /home/sultanbek/projects/hackathons/dt26-lab/runs/night.txt.
Read attempts/A20-night-orchestration/reports/personal.md first: the previous agent found that
W-NO-PERSONAL-ITEMS mostly fires on the money counting machine, which OWLv2's "handbag"/"a handbag"
prompt matches (box IoU with the calibrated counter 0.70-0.98 on Х-11, Х-13, Х-14, Х-15). Some of
those clips have no calibrated counter at all (X-1, Х-4/Х-47), so "overlaps the calibrated counter"
alone may not be enough. The team decided: correctness first. A personal-items finding that is
really the money counter must go, even if it costs catches on our 40 clips.

Part 1 (you own it): W-NO-PERSONAL-ITEMS and the calibration/detection handling it needs.
- Stop the money counter from counting as a personal item, in a way that works on unseen videos,
  including when the counter wasn't calibrated (e.g. a large static "handbag" on the desk that
  matches the counter prompt's candidates, or that sits where the counter's candidate boxes are;
  look at scene.candidates in the cache).
- Keep real personal items: Х-40's coat must stay caught (organizer 17 s).
- Report which clips lose their catch and their real violation from the team spreadsheet.

Part 2 (you own it): K-RECOUNT-BEFORE-SAFE for Х-13 (organizer 47 s): the cashier opens a green
collection bag, lays out the bundles (4-...) and puts the money in the safe without recounting
and recording it. Check whether bag open, cash/bundle, safe open and the counter signals are in
the cache, and whether the rule can catch Х-13 for its real reason without firing on clean clips.

Part 3 (report only, don't change these rules; other agents own them): for Х-11 (laptop left
unlocked, 18 s; L-PC-LOCKED), Х-15 (collection bag left on the desk when the cashier leaves, 15 s),
X-1 (manual recount after the machine, 22 s) and Х-4/Х-47 (previous client's cash left on the desk,
57/68 s; S-CLEAN-DESK-HANDOVER), list with numbers which signals the cache has at those times,
and what a rule would need to catch each one. The next round will use this.

Measure on the full data and on --drop 0.2 with seeds 0, 1, 2.
