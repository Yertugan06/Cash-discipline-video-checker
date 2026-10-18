# Knowledge Pack: provenance, open verification, open conflicts

`rulebook.yaml` is the one source for every rule and its legal basis (acts, verbatim norm clauses,
requirement, visible breach, what the video cannot show, lifecycle, F1 thresholds; see
`docs/adr/0001-rulebook-single-source.md`). `rules.yaml`, `norms.json` and the `rules` part of
`config/f1_codex.yaml` are generated from it; never edit those by hand.

```
.venv/bin/python scripts/build_knowledge.py            # regenerate
.venv/bin/python scripts/build_knowledge.py --check    # what tests/test_rulebook.py enforces
.venv/bin/python scripts/build_knowledge.py --freeze   # before submission: enabled rules must rest
                                                       # on human-verified norms and acts in force
.venv/bin/python scripts/render_rules_doc.py           # regenerates docs/RULES.md
```

Two separate facts per rule: `enabled` (F1 runs it) and `jury_eligible` (generated: enabled, and
every cited norm and its act human-verified). The service reports only jury-eligible rules unless
`RULE_SCOPE=detector` is set for an experiment, so a pending citation never reaches the jury as if
it were verified. With nothing verified, `RULE_SCOPE=jury` refuses to start.

The norm texts were first taken from the kit's `codex_verified.json` (now under
`archive/vm-copies/`); the rulebook keeps only the legal fields, so the build no longer reads the
archive. Sections below describe how the pack got its current content.

## Rule lifecycle

The pack currently mirrors all 21 rule IDs in the business workbook. Each entry carries separate
`business_status`, `implementation_status`, `enabled`, and `disabled_reason` fields. The F1 detector
checks these fields against the converted codex and evaluator registry at startup.

Fifteen rules are enabled. `L-SAFE-LOCKED-ON-LEAVE`, `C-DETECTOR-CHECK`, and
`W-NO-CAMERA-PHONE` are candidate/unimplemented. `S-NO-MERGE` has an F1 evaluator and is enabled.
`L-NO-BAG-ON-LEAVE` and `K-COLLECTOR-DOC` have evaluators but remain disabled because their legal
and video-visibility basis needs review. `C-REJECT-NOT-RETURNED` is confirmed business-side but has
no evaluator yet. Disabled rules carry a reason and are skipped by the evaluator.

## Three distinct statements (architecture.md §3)

`Knowledge.describe()` produces exactly two of the three statements (the third, citation, is
carried as separate `GroundedFinding`/`Violation` fields, not inlined into the description text):

1. **observation** -- `rule.description_template` filled from `Finding.facts` (+ `t` =
   `round(t_anchor, 1)`), e.g. "С 9.0 по 19.0 с кассир отсутствует на рабочем месте; на столе
   видны наличные.";
2. **claim** -- always the fixed sentence "Признаки возможного нарушения: `<title_ru>`.";
3. **citation** -- `rule.norm_ids[0]` resolves to a `NormRef` with structured KZ jurisdiction,
   document title, issuing authority, number, adoption date, clause, quote, URL, and citation status.
   Rule-to-clause strength (`direct`, `indirect`, or `weak`) lives on the rule because the same
   clause can support different rules with different strength.

## Human verification checklist

Every norm currently has `citation_status: "pending"`. A human must open the URL and confirm the
metadata, current clause text, and legal status before marking it `verified` with
`verified_by`/`verified_at`. A known incorrect citation should be `invalid`; the runtime refuses to
enable rules that rely on invalid citations.

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

   Until a human resolves this, `L-PC-LOCKED`'s citation remains pending review. `Knowledge.ground()`
   reports `citation_status: "pending"`.

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
