# data/

Team-owned inputs. The organizer dataset (videos and `open_labels.xlsx`) is
not in the repo: it lives on `datathon` in `~/data/open/` and is gitignored
here (`open/`).

| File | What it is | Used by |
|---|---|---|
| `Cash_Discipline_Cases_Rules.xlsx` | The team's rulebook. Sheets `README`, `Rules` (id, breach condition, min duration, norm), `Cases`, `Case_Rule` (case -> rules), `Clips` (per clip: label time and label, primary case, what is visible, duplicate of, camera layout), `Open_Questions` | `scripts/convert_codex.py` turns it into `config/f1_codex.yaml`, which sets the F1 rule thresholds. `validation/.../harness/gt.py` reads `Clips` for each video's camera layout |
| `Таблица_нарушений.xlsx` | The team's annotation of the violation videos (sheet `Нарушения`) and the clean ones (`Без нарушений`): second, what is visible, violation type, norm with adilet link, confidence, review notes, frame screenshots, violation/clean pair. Also sheets `Сравнение` and `Нормы` | `validation/.../harness/gt.py`: the `human` part of `gt.json` (event types, norm codes, reliability) and the clip groups that `split.py` uses for the dev/lockbox split |
| `prepared/videos.jsonl` | One record per organizer label row: id, path, sha256, duration, organizer verdict and seconds, duplicate group | `realtime/` gateway (`LABELS`) to show the organizer verdict next to each result; `scripts/replay_f1.py score --labels` |

Notes:

- Of the files here, only `Cash_Discipline_Cases_Rules.xlsx` changes what the service detects,
  and only after `scripts/convert_codex.py` is re-run.
- `prepared/videos.jsonl` was built by a `prepare_data.py` that is no longer
  in the repo; its other outputs are in `archive/data-prepared-old/`.
- The ground truth for verdict and timing is the organizer's
  `open_labels.xlsx`, not these workbooks (see `STATUS.md`).
