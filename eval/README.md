# eval/

Evaluation tooling. Kept out of `backend/` deliberately: `backend/` must never reference
`data/`, label files or `.xlsx` (architecture.md §2, enforced by `tests/test_no_label_access.py`);
`eval/` is explicitly allowed to.

- `kit_states_adapter.py` -- `load_kit_states(path) -> StateTimeline`: reads one of the kit's
  saved per-video JSON Lines state files (`reasearch2/.../runs/<run>/states/<video>.jsonl`,
  gitignored/private) and builds a typed `StateTimeline` for `backend.rules.evaluate`. Never
  prints a row's field values. Used by `tests/test_rules_equivalence.py`.
- `run_eval.py` -- takes a directory of API `DoneJob` JSON outputs (one file per video) and runs
  the R1 scorer (`reasearch1/validation-evidence/harness/score.py`) on them, by adapting each
  `DoneJob` to the harness's `{clip_id: {verdict, events, runtime_s, error}}` prediction format
  and writing it to `reasearch1/validation-private/preds/<name>.json`. Only ever prints the
  harness's own aggregate report. See the module docstring for CLI usage.

  ```
  .venv/bin/python -m eval.run_eval /path/to/done_jobs --split dev
  ```

  `--split lockbox` exists for the one-time, human-gated final scoring step only -- see the
  shared brief ("Never use the lockbox split for any choice") and `knowledge/README.md`
  ("Ranking policy"). Everyday runs should use `--split dev`.

`tests/test_eval_run_eval.py` exercises `build_pred`/`to_pred_entry`/`clip_id_from_filename`
against synthetic `DoneJob` fixtures and a synthetic GT/split pair written to a tmp dir -- never
against the real `reasearch1/validation-private/gt.json`.
