# Data preparation, Phases 1–2

Run `python3 prepare_data.py` from the repository root. It uses only the Python standard library and reads source files locally. The generated `videos.jsonl`, `events.jsonl`, and `validation_report.json` are written here. `python3 prepare_data.py --out /path/to/output` changes the output directory.

`schema.json` defines the two record types. `videos.jsonl` has one record per organizer label row, not one per unique byte stream. IDs normalize Latin `X` and Cyrillic `Х` to `X-###`. The SHA-256 digest identifies byte-identical media; `duplicate_group` links duplicated label records. Thus X-004 and X-047 retain their separate organizer timestamps on the same video content. Durations come from the MOV `mvhd` metadata atom. `organizer_label_raw` and `label_provenance` preserve the original labels.

`events.jsonl` has one record per actual observation row in the latest workbook (`Таблица_нарушений_v2.xlsx`): 22 from `Нарушения` and 19 from `Без нарушений`. The X-48 clean-sheet row only states that it duplicates X-5, so it is inventoried as a duplicate and listed as a skipped non-observation in the report. `observation.text` is the source wording. Optional `actor_role`, `action`, and `object_state` are literal structured transcriptions from the violation observation column. Null means no such field was annotated. `source_interpretation` retains the workbook's exploratory violation wording for traceability; it is **not** an organizer verdict or a legal conclusion. The organizer verdict lives only in `videos.jsonl`.

`anchor_sec` is the point timestamp written in the violation sheet and checked against the organizer label. `start_sec` and `end_sec` stay null because the workbook does not provide reviewed bounds for each complete event. Time ranges embedded in prose are preserved in `observation.text`; they are not silently converted to event intervals. Clean-clip observations have no event anchor even if their prose contains times.

`annotation_status` means:

- `human_reviewed`: the row contains explicit human agreement or review confirmation.
- `uncertain`: the row has a conflicting or unresolved review note.
- `needs_review`: the workbook contains an observation but no explicit final human confirmation.

These statuses do not change the organizer's verdict. Original confidence, annotation notes, reviewer notes, and worksheet cell locations remain on each event. The validation report checks inventory counts, ID uniqueness, file hashes, reference integrity, timestamps, missing fields, and duplicate-content verdict conflicts. Its `unresolved_review` list records manual decisions still needed.

For the existing Problem Validation workflow, join events to videos on `video_id`; group byte-identical clips by `sha256` when evaluating unique footage, but keep each original label and timestamp. Phase 3 can review uncertain rows, decide event boundaries and action taxonomy, and then design model or retrieval behavior. No model training or final pipeline is included here.
