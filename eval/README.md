# eval/

Evaluation tooling. Kept out of `backend/` deliberately: `backend/` must never reference
`data/`, label files or `.xlsx` (architecture.md §2, enforced by `tests/test_no_label_access.py`);
`eval/` is explicitly allowed to, and is the only place that reads organizer labels or human
annotations.

## Data and ground truth

The team data root has one layout everywhere (see `data.py`): `open/` (organizer labels and
videos) and `team/` (human annotations, the cases workbook, `reviews.json`). The team copy is
`datathon:~/data`; locally it defaults to `<repo>/data` (override with `DATATHON_DATA_ROOT`).
`data_manifest.json` pins the SHA-256 of every file.

```
.venv/bin/python -m eval.sync_data            # check the local copy (read-only)
.venv/bin/python -m eval.sync_data --remote   # also check the VM copy (read-only)
.venv/bin/python -m eval.sync_data --pull     # download missing files; never overwrites
.venv/bin/python -m eval.ground_truth         # build gt in memory, write discrepancies.json,
                                              # check the frozen split
.venv/bin/python -m eval.ground_truth --write # also rewrite validation-private/gt.json
```

- `ground_truth.py` replaces the retired `reasearch1/.../harness/gt.py` and keeps its output
  fields. Each `gt.json` entry is one unique video (by SHA-256), keyed by its lowest clip ID;
  `files` keeps every duplicate clip's own organizer label.
- `discrepancies.json` lists disagreements for people to review (organizer vs human annotation,
  duplicates whose labels differ, changes since the previous `gt.json`). Nothing resolves them
  automatically.
- Reviewer decisions live in `team/reviews.json`, never in code. After an agreed change, update
  its hash in `data_manifest.json` and copy it to `datathon:~/data/team/`.
- `split.json` is frozen. The builder re-derives it with the original algorithm and fails if it
  no longer matches; nothing writes it.
- Clip IDs are parsed only by `backend/clip_id.py` (`X-<n>`, Latin X).
- `coverage.py`: per violation video, whether and why the rulebook explains its annotated clause.
- `check_outputs.py <dir>`: checks saved API job results against the jury contract and each
  clip's own organizer label (verdict, timing, JPEG evidence, filled templates, citation,
  wall time). Prints structured facts only, never descriptions or frames; skips lockbox clips
  unless `--allow-lockbox`.
- `tests/test_dataset_real.py` checks the real data root and skips where it is absent.

- `kit_states_adapter.py` -- `load_kit_states(path) -> StateTimeline`: reads one of the kit's
  saved per-video JSON Lines state files (`archive/vm-copies/.../runs/<run>/states/<video>.jsonl`,
  gitignored/private) and builds a typed `StateTimeline` for `backend.rules.evaluate`. Never
  prints a row's field values. Used by `tests/test_rules_equivalence.py`.
- `run_eval.py` -- takes a directory of API `DoneJob` JSON outputs (one file per video) and runs
  the R1 scorer (`validation/validation-evidence/harness/score.py`) on them, by adapting each
  `DoneJob` to the harness's `{clip_id: {verdict, events, runtime_s, error}}` prediction format
  and writing it to `validation/validation-private/preds/<name>.json`. Only ever prints the
  harness's own aggregate report. See the module docstring for CLI usage.

  ```
  .venv/bin/python -m eval.run_eval /path/to/done_jobs --split dev
  ```

  Each event's code is its rule's primary norm id from `knowledge/rules.yaml` (`A-DOOR-LOCK` ->
  `14-16-1`), so the scorer's legal-citation line compares it with the annotated clause. A
  `<clip>.meta.json` with `wall_s` next to a result fills the scorer's runtime line.
- `export_gateway_run.py <state.json> <out_dir>` -- turns a saved realtime-gateway run
  (`datathon:~/realtime-state/state.<run>.json`) into that results directory: `<clip>.json` (the
  `DoneJob`, or a `FailedJob` with the gateway's error) and `<clip>.meta.json` (`wall_s`). Drops
  the gateway's label; refuses a run that has not finished.

  ```
  scp datathon:realtime-state/state.run4-leavefix.json /tmp/
  .venv/bin/python -m eval.export_gateway_run /tmp/state.run4-leavefix.json /tmp/run4
  .venv/bin/python -m eval.run_eval /tmp/run4 --name run4 --split dev
  .venv/bin/python -m eval.check_outputs /tmp/run4
  ```

  `--split lockbox` exists for the one-time, human-gated final scoring step only -- see the
  shared brief ("Never use the lockbox split for any choice") and `knowledge/README.md`
  ("Ranking policy"). Everyday runs should use `--split dev`.

`tests/test_eval_run_eval.py` exercises `build_pred`/`to_pred_entry`/`clip_id_from_filename`
against synthetic `DoneJob` fixtures and a synthetic GT/split pair written to a tmp dir -- never
against the real `validation/validation-private/gt.json`.
