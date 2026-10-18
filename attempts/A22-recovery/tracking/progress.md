# A22 tracking progress

Matcher limits frozen before real matcher outputs in matcher-limits.json.
CPU only; opt-in module and replay runner in progress. Combined source: shared/a22/base, main 5fae84bc10415111a04b5982d156727ca80f788a.
No old A21 events/rules will be imported by the replay. No production hook or service change.

04:29 UTC checkpoint: all six focused clips actually decoded/replayed on CPU. X4 gains one dual-seed/cycle-checked sample at56.5s and stops at56.0s (low NCC). It does not reach session2 start55.5 or prior exit53: no previous-session support and no finding change. Other five clips add no samples. Seven focused synthetic cases passed. Full40 is inexpensive (~13s/6), so the unchanged frozen matcher is now being run on all40 unique inputs.

04:31 UTC: full40 unique CPU replay completed in52.329s. Four appearance-supported new samples (X4 one; X13 three). No findings or handover event changes in all40. X4 stops56.0s and never supports previous cash before session2. Seven focused tests pass; archive/report prepared for review only. No promotion, runtime edits, GPU or service actions.
