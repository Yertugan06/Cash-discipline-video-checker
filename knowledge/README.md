# Knowledge Pack: provenance, open verification, open conflicts

`rules.yaml` and `norms.json` in this directory are **build outputs**. The runtime
(`backend/knowledge.py`) only ever reads these two files. They are rebuilt by
`scripts/build_knowledge.py` from:

- `archive/vm-copies/datathon/forte_brev_kit/brev_kit/codex/codex_verified.json` (217 rows, verbatim
  legal text + `act`/`punkt`/`url`/`strength` per norm) -- the source for every `norms.json` row;
- `config/f1_codex.yaml` (the F1 team's independent rule/citation research) -- used only to
  cross-check sources and to document the conflicts below, **not** used as the primary source
  for any `norms.json` row (several of its ids are not present in `codex_verified.json`, see
  "Open conflicts").

Re-run after editing the rule table in `scripts/build_knowledge.py`:

```
.venv/bin/python scripts/build_knowledge.py
.venv/bin/python scripts/render_rules_doc.py   # regenerates docs/RULES.md
```

## Canonical rule ids

18 rules, matching the kit short name -> canonical id mapping agreed in `architecture.md` §3 (the
mapping itself only exists as data in this file / in `scripts/build_knowledge.py`'s `RULES` table
and in the `backend/rules/timeline.py` constants -- there is no third copy). 17 are `enabled:
true`; `C-DETECTOR-CHECK` (kit's `no_detector`) is `enabled: false` because it is explicitly
flagged experimental by the kit (`EXPERIMENTAL = {'no_detector'}`) and checks a whole-video
condition with a single weak signal (never any `detector_in_use` observed anywhere).

`config/f1_codex.yaml` additionally defines three ids with no kit-side detection logic
(`L-NO-BAG-ON-LEAVE`, `C-REJECT-NOT-RETURNED`, `K-COLLECTOR-DOC`). They are **not** in
`rules.yaml`: nothing in this build implements them, and adding a rule_id with no detector behind
it would be a dangling, untestable entry. Adding them is a future decision, not resolved here.

## Three distinct statements (architecture.md §3)

`Knowledge.describe()` produces exactly two of the three statements (the third, citation, is
carried as separate `GroundedFinding`/`Violation` fields, not inlined into the description text):

1. **observation** -- `rule.description_template` filled from `Finding.facts` (+ `t` =
   `round(t_anchor, 1)`), e.g. "С 9.0 по 19.0 с кассир отсутствует на рабочем месте; на столе
   видны наличные.";
2. **claim** -- always the fixed sentence "Признаки возможного нарушения: `<title_ru>`.";
3. **citation** -- `rule.norm_ids[0]` resolved to a `NormRef` (`act`, `punkt`, `quote`, `url`,
   `strength`, `human_verified`), surfaced by the serializer as `source`/`source_url`/
   `source_quote`/`strength`/`citation_status` (WP1's `backend/serialize.py`), never embedded in
   the description text.

## Human verification checklist

**No norm in `norms.json` is `human_verified: true`.** An AI must never set that field (AGENTS.md
/ shared brief, rule 6). Every one of the 20 norms below needs a human to open the `url`,
confirm the `quote` is still the current text of `act`, `punkt`, and then flip `human_verified`
to `true` (with `verified_by`/`verified_at`) by hand -- not by re-running the build script.

| norm_id | act, punkt | used by (primary unless noted) |
|---|---|---|
| 231-20-2 | 231, п. 20 ч. 2 | L-NO-CASH-ON-LEAVE (primary), S-CLEAN-DESK-HANDOVER (primary), S-NO-MERGE, A-SECOND-PERSON |
| 231-22 | 231, п. 22 | L-NO-CASH-ON-LEAVE |
| 231-80-1 | 231, п. 80 | L-SAFE-LOCKED-ON-LEAVE (primary) |
| 53-71-9 | 53, п. 71 пп. 9) | L-PC-LOCKED (primary) -- **see conflict below** |
| 231-80-3 | 231, п. 80 | L-NO-DOCS-ON-LEAVE (primary) |
| 231-20-2b | 231, п. 20 ч. 2 | S-SAFE-CLOSED (primary) |
| 231-21 | 231, п. 21 | S-NO-MERGE, A-SECOND-PERSON |
| 14-16-1 | 14, п. 16 пп. 1) | A-OUTSIDER-ZONE (primary), A-DOOR-LOCK (primary) |
| 14-8-1 | 14, п. 8 ч. 1 | A-OUTSIDER-ZONE, A-DOOR-LOCK |
| 231-20-1 | 231, п. 20 ч. 1 | C-COUNT-BEFORE-EXIT (primary) |
| 231-19-1 | 231, п. 19 пп. 1) | C-ID-BEFORE-CASH (primary) |
| 231-7 | 231, п. 7 | C-ID-BEFORE-CASH |
| 231-19-2b | 231, п. 19 пп. 2) | C-DETECTOR-CHECK (primary, disabled rule) |
| 231-12-1 | 231, п. 12 ч. 1 | W-NO-PERSONAL-ITEMS (primary) |
| 231-12-2 | 231, п. 12 ч. 2 | W-NO-FOOD (primary) |
| 231-12-2b | 231, п. 12 ч. 2 | W-NO-CAMERA-PHONE (primary) |
| 231-24-3 | 231, п. 24 пп. 3) | K-SEAL-CHECK (primary) |
| 231-24-4 | 231, п. 24 пп. 4) | K-SEAL-CHECK |
| 231-74-1 | 231, п. 74 | K-RECOUNT-BEFORE-SAFE (primary) |
| 231-42 | 231, п. 42 | K-RECOUNT-BEFORE-SAFE |

## Open conflicts (do not resolve here -- a human must check adilet.zan.kz)

1. **Screen-lock norm, `L-PC-LOCKED`.** Three sources disagree:
   - the kit's `codex_verified.json` cites **`53-71-9`** (act 53, "п. 71 пп. 9)", quote about a
     30-minute inactivity auto-lock, `adilet.zan.kz/.../V2600038336`) -- this is what
     `rules.yaml` currently uses, because it is the only one of the three with a verified
     verbatim quote available to this build;
   - the R1 validation workbook (`validation/validation-evidence`) uses **`48-71-9`** instead
     (act 48, not 53) -- this id is **not present** in `codex_verified.json`, so no quote/URL
     could be filled in without inventing one, which this build will not do;
   - `config/f1_codex.yaml`'s own entry for `L-PC-LOCKED` cites `source: "NBRK 48, п.71 пп.9
     (repealed; successor to confirm)"`, `source_url: https://adilet.zan.kz/rus/docs/V1800016772`
     -- i.e. the F1 team's own candidate is act 48 under a *different* adilet document
     (`V1800016772`, not `V2600038336`), and flags it as repealed with an unconfirmed successor.

   **Candidates for a human to check on adilet.zan.kz, side by side:**
   - A: act 53 (`V2600038336`), п. 71 пп. 9) -- currently in `norms.json` as `53-71-9`;
   - B: act 48 (`V1800016772`), п. 71 пп. 9) -- in the R1 workbook and F1's `source`, marked by F1
     as repealed with the successor unconfirmed; not added to `norms.json` because no verbatim
     quote for it has been verified yet.

   Until a human resolves this, `L-PC-LOCKED`'s citation should be treated as unverified evidence
   of *a* workplace-security norm, not a confirmed specific clause -- it is already
   `human_verified: false`, so `Knowledge.ground()` reports `citation_status: "needs_review"`.

2. **Kit `CODEX` list vs. F1 `codex.yaml` `source` field, per rule.** The kit's own
   `timeline_rules.py` `CODEX` dict (what this build uses) and F1's `codex.yaml` `source` strings
   were produced by two different research passes and do not always agree on which NBRK act/punkt
   is the best citation for the same mechanism (e.g. `L-SAFE-LOCKED-ON-LEAVE` / F1's
   `L-SAFE-LOCKED-ON-LEAVE` cites п.20, п.78 vs. the kit's п.80; `S-SAFE-CLOSED` / F1's
   `S-SAFE-CLOSED` cites п.20 only, matching the kit here). `rules.yaml` currently follows the
   kit's `CODEX` list throughout (it is the system whose timeline logic this module ports, so its
   citations are the ones empirically tied to the detection condition). A full line-by-line
   kit-vs-F1 citation diff, and the final choice per rule, is left to a human doing the
   verification pass above -- this file only flags that the two sources exist and can disagree.

## Ranking policy

`backend/rules/ranking.py` implements exactly one policy: sort by `Finding.rank_score` descending
(persistence -- the count of sampled times that supported the finding), then by position in
`rules.yaml` (its declaration order, top to bottom) as the tie-break, then cap to `cap` (default
3). This is frozen for dev. Any tuning of the ordering (e.g. weighting rule severity, or a
learned score) is a **later, human-gated step**: it must be chosen on the dev split only and
scored once on the lockbox split, per the shared brief ("Never use the lockbox split for any
choice" until that one-time, human-approved step).

## Equivalence with the kit

`tests/test_rules_equivalence.py` runs the kit's own `timeline_rules.detect()` (loaded via
`importlib` from the gitignored `archive/vm-copies/` tree, skipped with a clear reason when absent) as
the reference oracle, and `backend.rules.evaluate()` as the port, over every saved state file
under `runs/q35_9b_fp8/states` (40 files; `KIT_STATES_DIR` overrides the path). As of this build,
**all 40 are bit-identical** (same `(rule_id, t_anchor)` set, `experimental=True` so
`C-DETECTOR-CHECK` is included in the comparison even though it ships disabled). No behavioural
deviation was needed, so there is nothing further to document here beyond the two
signal-processing constants (`SMOOTH_K`, `DEDUPE_S`) and the shared-threshold "owner rule" choices
already explained in `backend/rules/timeline.py`'s module docstring.

A separate, optional check (not a test -- it touches `validation/validation-private`, which is
outside this module's file set) ran `validation/validation-evidence/harness/score.py` against the
40-video ranked output of this port (`rank(evaluate(...), rules, cap=3)`, one event per finding,
`code` = the finding's primary norm id). Aggregate result, labels never printed, matching the
measured basis in `architecture.md` §4 closely:

```
video  TP=19 FN=2 FP=16 TN=3 | recall 19/21 | acc 22/40
loc[N.0] any-event: ±3s 12/22   (architecture.md's own measured range: 13-14/22)
mechanism (reliable subset n=17): human norm-1 code among predicted codes 8/17, within ±3s 5/17
```

The scorer has since renamed that last line `legal-citation match` (same computation): it measures
whether a predicted citation shares the clause of the human annotation's first norm, not whether the
violation type is right.
