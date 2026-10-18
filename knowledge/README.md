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

## Legal sources and the catalog

The texts of the three acts are stored in `sources/<act>/source.docx` (adilet.zan.kz exports of the
current редакция, downloaded 2026-10-18; provenance in `sources/sources.yaml`). The site serves
texts only through a JavaScript app and a keyed API, so nothing re-downloads them: to refresh an
act, download it again and replace its `source.docx`.

```
.venv/bin/python scripts/build_legal_catalog.py          # regenerate the files below
.venv/bin/python scripts/build_legal_catalog.py --check  # what tests/test_legal_catalog.py enforces
```

| file | what it is | edited by |
|---|---|---|
| `sources/<act>/text.txt` | the act as plain text, Word list numbers restored | generated |
| `legal_catalog.json` | every punkt with its parts (`231-20-c2`) and subpunkts (`231-19-s1`), footnotes, the rules citing it and its review | generated |
| `legal_review.yaml` | per punkt: applicability, observability, status (`linked`, `candidate`, `weak`, `excluded`) and a reason. Machine-proposed (LLM reading of the text), for a human to confirm | by hand |
| `active_rules.json` | enabled rules with each norm's strength, `citation_status` and the source check; `status: needs_review` until every norm is human-verified | generated |
| `event_mapping.json` | per F1 rule: the evaluator, the event kinds (`backend/f1/events.py`), detector labels (`config/perception.yaml`), roles and coverage it reads, parsed from `backend/f1/rules.py` | generated |
| `legal_audit.md` | the checks above as tables, plus the excluded punkts by reason | generated |

The source check finds each rulebook `quote` verbatim (ignoring whitespace, case, dash style) in
the punkt, part or subpunkt its `punkt` field names. `tests/test_legal_catalog.py` fails if a quote
is not in the act, sits in a different punkt, or cites the repealed act 48. It is a check of the
text only; `citation_status: verified` still needs a person on adilet.zan.kz.

### Integration with the backend

Nothing at runtime changes: the service reads `rules.yaml`/`norms.json` (built from the rulebook)
and never these files, and no LLM or search runs during analysis. The F1 detector emits a finding
per rule id; that rule id is the event type, and `Knowledge.ground()` attaches the rulebook norm.
To add or change a citation:

1. Find the unit in `legal_catalog.json` and copy the clause text verbatim into a rulebook norm
   (`act`, `punkt` as "п. N", "п. N ч. K" or "п. N пп. K)", `quote`, `url`).
2. Run `scripts/build_knowledge.py`, `scripts/build_legal_catalog.py`, then `pytest`.
3. A person checks the clause on adilet.zan.kz and sets `citation_status: verified` with
   `verified_by`/`verified_at`.

To turn a `candidate` punkt into a rule, the detector first has to emit the events it needs;
`event_mapping.json` lists what the current evaluators read.

### Source check (2026-10-18)

- All 20 rulebook quotes are verbatim in the punkt, part or subpunkt they cite, in the редакция
  stored here (231: latest amendment in its footnotes 30.06.2026 № 78; 14: 24.12.2024 № 88; 53 has
  no amendments). The `#z…` anchors in the URLs were not checked: the site cannot be read offline.
- Act 48 (`V1800016772`) is repealed by act 53 (п. 2 of the постановление; the appended list, item
  1). It is recorded in `sources/sources.yaml` as never-cite, and the source check rejects it.
- `L-PC-LOCKED` now cites `53-71-9` as `weak` (was `indirect`). Пп. 9 п. 71 sets how the system
  locks a session after 30 minutes of inactivity. It does not say that a cashier must lock the
  screen when leaving, and 30 minutes do not fit in a clip of at most 145 s. Act 53 has no
  lock-on-leave duty (searched for блокир/покида/оставл/экран). The rule stays enabled.
- Every punkt of the three acts has a review in `legal_review.yaml`: 231 (133 punkts plus 21
  inserted by amendments, such as 53-1 or 109-1..11) has 10 linked, 4 candidates and 140 excluded;
  14 has 2 linked and 22 excluded; 53 has 1 weak and 161 excluded.
  Candidates without a rule: 231-9 (equipment to check authenticity), 231-25 (opening a damaged
  bag in front of the collectors), 231-107/108 (the collection crew checks the bag and seal).
- The reviews were proposed by an LLM reading the stored text and spot-checked. Two of its
  proposals were rejected on the text (53-75 external media as a basis for `W-NO-CAMERA-PHONE`;
  53-136 software installation as a candidate). The act 14 reasons are in English.
- `states_used` in the rulebook is the VLM-era vocabulary. What F1 actually reads is in
  `event_mapping.json`.

### Requirements and coverage (2026-10-18, second pass)

`legal_requirements.yaml` holds 77 atomic requirements derived from the acts without looking at
the rulebook or the detector (three LLM readers, one per part of the acts). Each quote is checked
verbatim against its unit, and each requirement has a `decision` against the rulebook and
`backend/f1/rules.py`. `coverage_matrix.md` (generated) shows both directions: law -> rule ->
F1 events -> tests, and rule -> requirements found for it. Its tests column greps `tests/`, so
rebuild the catalog after editing tests.

Outcome: 8 requirements implemented, 4 implemented with a weak basis, 4 need new detection logic,
48 cannot be verified from video, 13 are not about the cash desk.

Changes made from it:
- New rule `L-LEFT-DURING-SERVICE` (231 п. 22, direct). It fires when the cashier makes a confirmed
  exit while a client session is open, and stays silent when `L-NO-CASH-ON-LEAVE` reports the same
  leave. Before this, п. 22 was covered only together with cash on the desk. It ships
  `enabled: false`. The replay (`attempts/A22-left-during-service-replay/`, run with
  `scripts/replay_f1.py run --enable L-LEFT-DURING-SERVICE`) gave no finding: in the open clips
  every cashier leave happens when no client session is open. Verdicts, false alarms and
  timecodes were unchanged, before and after merging A21 (32/40, then 30/40, 0 clean false
  alarms both times). Since A21 the rule takes confirmed room exits only (`ctx.room_exits()`) and
  ignores an exit at the very end of the recording. Enabling it is a human decision.
- Strength lowered to `weak` where the norm does not state the behaviour the rule detects:
  `A-OUTSIDER-ZONE` (14 п. 8, п. 16 пп. 1) are about how the room is built),
  `A-SECOND-PERSON` (231 п. 20 ч. 2, п. 21: nothing about one client at a time),
  `K-RECOUNT-BEFORE-SAFE` (231 п. 42: a controller's presence, not a recount before the safe),
  `L-NO-DOCS-ON-LEAVE` (231 п. 80 refers to the bank's internal documents).

Left as they are, for a person to decide: `A-SECOND-PERSON`, `W-NO-FOOD` and `L-PC-LOCKED` have no
requirement that the independent reading found. Deferred (`new_needs_logic`):
- `W-NO-CAMERA-PHONE` (231 п. 12 ч. 2): OWLv2 detects `phone`, but `events.py` emits no event for it.
- Identification and recount before a payout (231 п. 31 пп. 1), 4)): payout handovers cannot yet be
  told apart from returned documents, and п. 32 exempts intact packs.
- Key left in the safe (231 п. 76): there is no key detector.

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

`Knowledge.describe()` joins the three statements into the jury `description`, each behind a
label, e.g. "Что видно: С 0:09 по 0:19 кассир отсутствует на рабочем месте; на столе видны
наличные. Возможное нарушение: <title_ru>. Норма: Правила осуществления кассовых операций ...,
п. 20 ч. 2 (Правление Национального Банка Республики Казахстан, № 231 от 29.11.2019)."
The same pieces also travel as separate `Violation` fields, so the UI never parses the text:

1. **observation** (`GroundedFinding.observation`, `Violation.observation`) --
   `rule.description_template` filled by `Knowledge.ground()` from `Finding.facts`. Times are
   `m:ss` (`knowledge.clock()`): `{t}`, `{t_start}`, `{t_end}`, and `{interval}`, which reads
   "С 0:09 по 0:19", or "В 0:09" when the interval is a single moment;
2. **claim** -- "Возможное нарушение: `<title_ru>`.";
3. **citation** -- `rule.norm_ids[0]` resolves to a `NormRef` with structured KZ jurisdiction,
   document title, short title (`acts.<n>.short_title`), issuing authority, number, adoption date,
   clause, quote, URL, and citation status; `knowledge.citation()` turns it into the readable
   reference above. `Violation.legal_basis` lists every cited norm, primary first.
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

   **Update 2026-10-18 (source check above):** B is ruled out because act 53 repealed act 48. A's
   quote is verbatim in the stored act 53, now with strength `weak`. A person still has to mark it
   verified.

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
