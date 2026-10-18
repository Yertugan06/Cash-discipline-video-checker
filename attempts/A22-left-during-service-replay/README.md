# A22 - L-LEFT-DURING-SERVICE replay

- **Date / who:** 2026-10-18, agent (offline replay on `datathon`, approved by the user)
- **Status:** measured, rule stays disabled
- **Where it ran:** `datathon:~/legal-replay-20261018/` (copy of `backend/`, `config/`, `knowledge/`,
  `scripts/` from the working tree on branch `fix-dataset`, uncommitted, on top of `2c5db9a`);
  throwaway container `forte-cash-checker:cuda` with `--network none`, `datathon26_work` mounted
  read-only. Production config, service and gateway untouched.
- **Models:** none run; cached F1 perception of the deployed image (RT-DETR, OWLv2, CLIP, RTMPose)

## Approach

The new rule `L-LEFT-DURING-SERVICE` (231 п. 22, from the legal review in
`knowledge/legal_requirements.yaml`, R-231-22-a) fires on a confirmed cashier exit while a client
session is open, and is silent when `L-NO-CASH-ON-LEAVE` reports the same leave. Both runs use
the same code; the second only adds `--enable L-LEFT-DURING-SERVICE`.

## How to reproduce

```
D=~/legal-replay-20261018
docker run --rm --network none --entrypoint "" -v datathon26_work:/app/runtime:ro \
  -v $D/src:/work:ro -w /work -e PYTHONPATH=/work -e API_KEY=x forte-cash-checker:cuda \
  python scripts/replay_f1.py run [--enable L-LEFT-DURING-SERVICE] > out.jsonl
python scripts/replay_f1.py score out.jsonl --labels data/prepared/videos.jsonl
python scripts/replay_f1.py timing out.jsonl --labels data/prepared/videos.jsonl
```
`logs/diag.py` (mounted at `/diag.py`) counts why the rule did or did not fire.

## Results

| Metric | Baseline | + L-LEFT-DURING-SERVICE |
|---|---|---|
| Correct verdicts /40 | 32 | 32 |
| Recall (violation videos) | 13/21 | 13/21 |
| Clean false alarms | 0/19 | 0/19 |
| Timecode, caught clips within ±1 / ±3 / ±5 s | 7 / 11 / 13 of 13 | same |
| Replay time, 42 cache entries | 3.3 s | 3.3 s |
| Findings of the new rule | - | 0 |

The two outputs are byte-identical. Diagnostics over the 42 cache entries: 22 cashier leaves of
at least 3 s, 16 of them with a confirmed exit, 19 client sessions in all; but every one of those
22 leaves is in a clip where the event builder opened no client session. So no leave falls inside
a session. As a result there is no type, timing or duplicate effect to measure, and nothing overlaps
`L-NO-CASH-ON-LEAVE` (0 suppressed).

## Re-run on main after A21 (`5fae84b`)

The teammate's A21 (`attempts/A21-deadline/`) changed exits: documents and laptop rules now need a
confirmed room exit (`ctx.room_exits()`), and a recording that ends is not an abandonment. The rule
was aligned with that: it now takes `ctx.room_exits()`, ignores an exit less than
`min_duration_sec` before the end of the recording, and is silent when `L-NO-CASH-ON-LEAVE`
reports anything in the same absence. Replayed in `datathon:~/legal-replay-20261018-merged/` under
the same conditions (merged working tree, same image, cache read-only, `--network none`).

| Metric | Baseline (merged) | + L-LEFT-DURING-SERVICE |
|---|---|---|
| Correct verdicts /40 | 30 | 30 |
| TP / FN / FP / TN | 11 / 10 / 0 / 19 | same |
| Timecode, caught clips within ±1 / ±3 / ±5 s | 5 / 9 / 10 of 11 | same |
| Findings of the new rule | - | 0 |

The baseline matches A21's own result (30/40, 11 / 10 / 0 / 19), so the merge kept it. Outputs
with and without the rule are byte-identical. Diagnostics (`logs/merged/diag.py`): 14 confirmed
cashier room exits, all in the 28 cache entries without a client session; the 14 entries with
sessions (19 sessions) have no cashier exit. The rule's condition never occurs in the open clips.

## Logs

- `logs/baseline.jsonl`, `logs/with_rule.jsonl` - replay lines per cache entry
- `logs/diag.py` - the diagnostic script (counts only)
- `logs/merged/` - the same three files for the re-run on main after A21

## Conclusion

On this dataset the rule adds no catch and no false alarm. In the open clips the cashier leaves
when no client is being served, or the client is not recognised as a session. It stays
`enabled: false`; whether to enable it for unseen videos is a human decision, not a consequence
of this replay. A clip where the cashier walks out on a seated client would be needed to see it
work end to end.
