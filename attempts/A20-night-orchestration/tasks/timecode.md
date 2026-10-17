# Your assignment: timecodes and evidence anchors, branch orch/timecode (from night)

Baseline (night): {"videos": 40, "correct": 29, "clean_false_alarm": 2, "missed": 9}; per clip:
/home/sultanbek/projects/hackathons/dt26-lab/runs/night6.txt. The jury gives 15 of 100 points for timecode accuracy and evidence-frame
relevance. The organizer gives one second per violation clip (organizer_timestamps in
data/prepared/videos.jsonl). The team sheet says what happens when.

1. Write a small scorer (`scripts/replay_f1.py` subcommand `timing`, or a separate
   eval script) that, for each caught violation clip, reports each rule's anchor vs the organizer
   second: the best |offset| per clip, the mean, and within ±1/±2/±3/±5 s. Add a unit test.
2. Look for systematic, explainable offsets per rule (e.g. a leave rule anchoring at the moment
   the cashier stands up vs the moment they are gone, or a rule anchoring at the start of a
   condition when the violation becomes visible later). Fix only anchors whose rule meaning
   supports it, and don't move anchors toward the label without a reason in the rule's semantics.
3. When several findings exist in one clip, check the ranking (backend/rules/ranking.py)
   puts the most relevant one first. That's the one the UI and evidence show.

You must not change any verdict: the full-data and drop-0.2 seed 0/1/2 verdicts must stay
identical; only finding times or order may move. Report the timing table before and after.
