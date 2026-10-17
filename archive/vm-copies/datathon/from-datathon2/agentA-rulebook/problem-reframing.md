# Problem Reframing — Datathon 26 (ForteBank): cashier-discipline violations from video

Source: `task.md` (brief + FAQ). Section/FAQ numbers below refer to it. The dataset is **not yet in `data/`**, so nothing here comes from looking at the clips. Revision 2: a critical self-review changed sections 3–7 (see §8, Revision log).

## 1. Challenge and objective

**Explicit requirement (must ship):** a locally-run service with a web UI and an API-key-protected two-step API (`POST /api/v1/analyze` → `job_id`; `GET /api/v1/jobs/{id}` → `processing|done|failed` plus the result). For each uploaded `.mov` it returns a per-video verdict (`violation` / `no_violation`) and, for each detected event: `type`, `timecode_sec`, `description`, and 1–3 base64 JPEG evidence frames. The UI also has to show the rule and normative source (document + clause) (§4, §5, §10). No cloud AI, no internet access needed after weights are loaded, no face identification, no audio (§7, FAQ 21, 28, 29). Each video has a 5-minute budget, and it has to sit behind a public URL (FAQ 14, 23).

**Desired outcome (interpretation):** cut reviewer time. Point a human to *the moment* and *the rule*, without overclaiming. The output is a hint, not a legal finding (§7).

**Problem type:** sparse **event detection and grounding** with an **open label set**, scored **automatically** on 5+ unseen videos, one of them from a new camera angle. It is less a classification problem than it looks: training labels have no type (FAQ 2), and test videos may contain types not in training (FAQ 9).

## 2. Evidence map

| Item | Status | Why it matters |
|---|---|---|
| ≥40 clips, 10–145 s, ≥29 fps, no audio, ~29 MB, overhead single camera, one cash desk; cashier, clients, cash-in-transit collectors in frame (FAQ 1, 3) | explicit | Sets the observable world and the compute budget |
| Staged footage (FAQ 3) | explicit | Violations may be exaggerated or shown unusually clearly, and confounded with the staging (actors, clip length, props) |
| Labels = per-video "violation" + timecode, **no type** (FAQ 2) | explicit | The violation taxonomy has to be discovered or built |
| Dataset includes correct-procedure clips as well as violation clips (§3) | explicit | Negatives exist; balance unknown |
| Open set of types; test may hold unseen types (FAQ 8, 9) | explicit | A closed-set model can't reach full recall |
| Final video from a different angle (FAQ 4) | explicit | Robustness (10 pts) plus detection on that video |
| Every dataset violation has a public KZ norm (FAQ 32); only RK acts (FAQ 30); clause-less refs and other banks' public docs accepted (FAQ 31) | explicit; FAQ 30 vs. 31 slightly in tension | Rule grounding is achievable; invented citations get penalised (criterion 4) |
| Missing a violation is unacceptable; false positives should be minimal (FAQ 16) | explicit, in tension | Asymmetric cost, with recall first. No numeric trade-off is given (see §6.3) |
| Detection is scored on the per-video verdict (FAQ 15) | explicit | 25 pts depend on one bit per video |
| Test set is 5+ videos (FAQ 12) | explicit | Small sample: each verdict is worth roughly 5 of the 25 detection points, if videos are weighted equally (derived; the weighting isn't stated) |
| Timecode tolerance not disclosed: "specify a concrete frame and timecode" (FAQ 17) | unknown | Localization strategy (peak vs. onset) depends on how the labels are defined |
| How a free-text `type` is judged (FAQ 18 says "automatic"; FAQ 8 says no closed list) | **unknown** | 15 pts depend on a method we can't see. A fixed reference list is **one hypothesis among several** (§4.1, item 2) |
| Timecode for omission violations is up to the team (FAQ 10) | explicit | The jury's labels still pick *some* convention; the dataset is the only clue |
| FAQ 11/15 mention "insufficient data", but the API has only two verdicts | explicit inconsistency | Uncertainty has to go into a binary verdict plus the description, not a third state |
| Claiming violations that depend on invisible data (postings, reconciliation) is forbidden (§7) | explicit | Some real regulatory violations are out of scope by definition |
| No face identification (FAQ 29) | explicit | "Unauthorized person" type rules can't rest on identity, only on visible role cues. Locating people/hands isn't identification, but the line has to be argued explicitly |
| How criteria 2–3 score videos with several events: matching rule, whether extra or missed events cost points | unknown | Decides whether reporting more candidate events is free or penalised |
| Compute and hosting available to the team | unknown | Decides whether the 5-minute budget is tight or comfortable |
| Team: 4 people, 24 h, heavy use of AI assistants for development/coding only (user) | explicit | Writing code is cheap. Evidence (watching footage, verifying law, hosting, end-to-end checks) and integration become the bottleneck |
| Cloud AI is banned *in video processing*, including passing it video, frames or their descriptions (§7); disqualification for cloud API use (FAQ 35) | explicit | Guardrail, not an open question: dataset video and frames stay out of cloud tools, including coding assistants. Team humans review the footage. Coding help is unaffected |
| AI-assisted legal research can produce plausible clauses that don't exist | likely | Criterion 4 penalises invented citations. Every clause needs a human to check it against the act's text on adilet.zan.kz |
| Deadline is 12:00 (FAQ 33), inside the 24 h window | explicit | Scope; decision gates must fall early |
| Disqualification for "ready-made solutions" (FAQ 35) vs. open-source pretrained models allowed (FAQ 24) | likely means turnkey commercial products/APIs | Licenses must allow commercial use |

### 2.1 Dataset facts (measured, `data/open/`; revision 4)

From the labels file and the `.mov` container headers only. **No frames were viewed.**

| Fact | Evidence | Consequence |
|---|---|---|
| 42 files and 42 label rows, matched one-to-one. Prefixes mix Latin `X` (X-1, X-2) and Cyrillic `Х` (the rest), consistently in both | `open_labels.xlsx`, filenames | Data hygiene only |
| **Two byte-identical duplicate pairs**: Х-4 ≡ Х-47, Х-5 ≡ Х-48 (same md5) → **40 unique videos** | md5sum | Effective n is 40. Duplicates must not be counted twice in any evaluation |
| **Х-4 and Х-47 are the same file, labelled "violation" at 57 s and at 68 s** | labels | Either one video holds **≥2 violations, with each row labelling one of them**, or the labels are noisy. This bears directly on the multi-event question and on how precise labels are. Resolve by a person watching both moments |
| 21 violation / 19 clean unique videos | labels | Training is roughly balanced. "Always violation" gets 52.5 % here. Test balance is still unknown |
| Exactly **one integer-second timecode** per violation row ("22 секунда"); clean rows have none | labels | Label resolution is 1 s, but FAQ 17 asks for a concrete frame. "The Nth second" could mean N.0 or [N−1, N) |
| Label times 5–68 s; 18 of 22 fall in the first 20 s; label time / duration ranges 0.23–0.94 | labels + durations | Events don't sit at a fixed relative position |
| Durations 11.6–142.5 s; sizes 2.4–28.7 MB; 21.7 min of unique footage in total | container headers | The footage pass (E2) is about 5–6 min of footage per person for 4 people |
| **Duration confound:** violation clips are shorter (median 20.4 s vs. 26.4 s clean). A duration-only threshold classifies 70 % of the 40 unique videos correctly, against the 52.5 % majority baseline | derived, small n | A **moderate shortcut is present** (E3 partly confirmed). Anything learned from the labels can pick up clip length rather than behaviour |
| Clip numbering has gaps (6, 7, 9, 36, 41, 42) | filenames | *Inference, unverified:* they may be held out for the test set, which would fit "similar videos" (FAQ 4) |
| FPS and resolution | not extracted yet | Still to measure (brief says ≥29 fps) |

## 3. Success measures

| Outcome (what matters) | Observable proxy (what is scored) | Baseline | Judging weight |
|---|---|---|---|
| Reviewer catches every real violation | Per-video verdict correct on test set | Trivial "always violation" gets every violation video right and fails every clean one. Its score depends on the unknown test class balance | 25 |
| Reviewer lands on the right moment | `timecode_sec` within an undisclosed tolerance; evidence frame shows the event | None given | 15 |
| Reviewer knows *what* went wrong | `type` judged correct by an undisclosed method | None given | 15 |
| Reviewer trusts the rule link | Real document + clause, interpretation correct, no invented claims | Penalty for fabrication | 15 |
| Works on new footage | Performance on unseen and new-angle video | Training-set performance (to be measured) | 10 |
| Usable product | UI clarity, upload/processing reliability, finishes within 5 min | — | 10 |
| Sound, local, extensible design | Locality compliance, rationale | — | 10 |

No targets are invented here. The only hard numeric constraint is the 5-minute budget per video.

**Small-sample consequence (derived):** with about 5 test videos, scoring is about not failing on any single video, not about average rates. One wrong verdict costs about the same as one in five. The new-angle video is one of those five.

### 3.1 Hackathon proxy vs. the bank's operational problem

| Dimension | What the hackathon scores | What the bank actually needs | Do they diverge? |
|---|---|---|---|
| Base rate | Staged, violation-dense clips | Long real footage where violations are rare | **Yes.** In operation, false positives dominate reviewer workload far more than the test set reveals |
| Footage | 10–145 s clips, one desk | Hours, many branches and cameras | Yes. Localization and robustness matter more in operation |
| Taxonomy | A `type` the scorer accepts (method undisclosed) | Map each event to the bank's regulatory obligations | Unknown until E1. A type named after the rule may serve both, or may not |
| Cost of a false positive | Lost verdict points | Reviewer time to dismiss it, which depends on how quickly the evidence lets them reject it | Yes. The bank's cost is about how verifiable a flag is; the score just counts errors |
| Explanation | Criterion 4 + description | Defensible, auditable, non-accusatory output (§7) | Aligned |
| Extensibility | Criterion 7, the pitch tie-break (FAQ 20) | Adding rules and cameras later | Aligned |

Implication for framing: optimize scoring proxies **where they don't conflict** with the operational problem. Where they do conflict (names that mimic scenarios, behaviour tuned to the dataset's base rate), record the conflict instead of quietly choosing the proxy. The pitch and criterion 7 reward the operational view.

## 4. Challenge to the framing

### 4.1 Central questionable assumptions

1. **"This is a video classification problem: learn violation classes from the training clips."** *Unverified; partly incompatible with the brief.* Labels carry no type, the label set is open, and unseen types are expected (FAQ 2, 8, 9). A closed set caps recall below what FAQ 16 asks for, and ~40 single-angle clips give little basis for angle robustness.
2. **"Type naming is cosmetic"**, and its mirror image, **"there is a hidden type list to match"**. *Both unverified.* FAQ 18 says only that scoring is automatic and that the result is JSON in a fixed schema. That fixes the **format**, not how the `type` string is judged. The facts are compatible with several mechanisms, none of them supported over the others:
   - (a) exact or normalized string match against a fixed reference list;
   - (b) similarity to a reference *description* rather than a name;
   - (c) mapping to a few coarse categories;
   - (d) "automatic" applies to verdict and timecode, while type is checked differently (rubric, sampling) or only loosely;
   - (e) partial credit.

   (a) is not established; FAQ 8 ("no closed list") makes it, if anything, less likely. **No framing choice should rest on (a) until E1 answers.** Until then, a `type` has to be defensible on its own: what was seen, and which rule. That holds under every mechanism above.
3. **"A clean video is lost only through false positives."** *Corrected from revision 1, which wrongly called false positives the main way to lose verdict points.* A violation video is lost by missing every event in it, and a clean video by any confident false event. Which failure dominates depends on the unknown test balance.

### 4.2 Mechanism vs. staged scenario

The unit of analysis can be set at three levels. Only the middle one has a **definition** that can carry over to a new scene:

| Level | Example (illustrative, not taken from data) | Does the *definition* carry over to a new angle/scene? | Citable? |
|---|---|---|---|
| **Staged instance** | "Actor X leans over the left counter at second 11 in the blue-shirt clip" | No. This is memorization | No |
| **Violation mechanism**: a relation among roles, objects, zones and time that a rule forbids or requires | "Valuables left accessible while the responsible role is absent"; "a required control step absent before handover" | Yes, if its predicates don't depend on image geometry | Yes, via the clause that defines it |
| **Abstract rule** | "Ensure safekeeping of valuables" | Yes, but too vague to observe | Yes |

**Two separate transfer questions. Don't merge them:**
1. **Definition transfer:** can the violation be *described* without reference to this viewpoint or scene? The §4.2 test below answers this, on paper.
2. **Recognition transfer:** can the roles, objects, zones and actions that the definition refers to actually be *perceived reliably* from another angle? A viewpoint-independent definition guarantees nothing here. A new angle changes occlusion, apparent size, what is visible inside the cash area, and which cues tell roles apart. **Only footage from another angle can answer this.** The training set has a single overhead view (FAQ 3), so it holds no evidence on it either way.

Passing question 1 is necessary for robustness but not sufficient. Every claim of angle robustness in this document refers to question 1 unless it says otherwise.

**Test for memorization vs. mechanism:** can the type's definition be written *without* naming anything specific to this scene (actor, desk side, pixel region, prop, clip duration), using only roles, object classes, zone semantics and temporal order? If not, it is a staged instance. A second test: does the definition predict a variant of the scenario that **wasn't** staged? A mechanism does; a memorized scenario doesn't.

**Shortcut risk in staged data (unverified):** violation clips may differ from clean ones in ways unrelated to the violation, such as duration, actors, camera exposure, or how many people are in frame. If they do, anything learned from the labels can score well on training and still fail on the test set. This is cheap to check (§6.4, E3).

### 4.3 Observation → interpretation → normative judgment

Every reported event crosses three layers, and each crossing is a place where unsupported assumptions get in:

| Layer | What it contains | Where unsupported assumptions occur |
|---|---|---|
| **Observation** (visible facts) | Persons and hands in regions, objects moving, time intervals, presence or absence *in frame* | **Absent from frame ≠ absent from the room** (worse from a new angle). **Not seen ≠ not done**: occlusion, especially for omissions |
| **Interpretation** (what the facts mean) | Role (cashier / client / collector), object class (cash, bag, document, key), zone meaning (restricted area, counter), action meaning (counting, handing over) | **Role without identity**: roles must come from visible cues such as position, uniform, or behaviour, since faces are excluded. **Object identity**: cash vs. paper. **Zone semantics**: where the restricted area is depends on the scene layout. **Intent**: never observable |
| **Normative judgment** (it may breach clause X) | Rule applicability + all conditions met | **Scope of the act**: does it apply to this kind of premises and operation? **Invisible preconditions**: authorization, exceptions, system state (§7). **Interpretive leap**: the clause may be broader or narrower than the observed act |

Consequences for the problem, not the solution:
- A `description` has to keep the layers apart: what was seen, what it was taken to mean and on what visible basis, and which rule it **may** correspond to.
- **A violation claim bundles three separate claims, each with its own confidence:**
  1. **Action confidence:** the action or state actually happened as described. This covers the observation and interpretation layers.
  2. **Impropriety confidence:** that action is improper in this context. The applicable rule's conditions are met, and no invisible precondition (authorization, exception, system state) could make it legitimate.
  3. **Citation:** the specific clause has been located and checked.
- **An unusual action is not a detected violation.** High (1) with unsupported (2) is an observation, not a violation. Reporting it as one would breach §5 ("no unconfirmed assumptions") and §7.
- **Where (2) can come from:**
  - (i) a located clause whose scope and conditions fit (B);
  - (ii) the organizers' own labelling: a training mechanism labelled "violation", which FAQ 32 says rests on a public norm even before we find it (C′);
  - (iii) nothing. A behaviour that is merely atypical has no source for (2).
- **What decoupling (3) may and may not do:** a missing citation should not suppress a detection whose (1) and (2) are supported, via source (i) or (ii). Suppressing it would trade a miss (FAQ 16) for a citation gap. That is the narrow sense in which revision 1's "only if cited" rule is withdrawn. **Decoupling (3) never licenses claims where (2) has no source.**
- This makes the brief's recall-vs.-no-unconfirmed-claims tension explicit. It **cannot be settled by lowering the bar for (2)**. See §6.3.
- A judgment that needs an invisible precondition can't be claimed (§7). It can at most be described as "visible conditions consistent with X; Y not verifiable from video".

## 5. Alternative framings (revised)

| # | Framing | Research question | Opportunity | Blind spot | Must-haves intact? |
|---|---|---|---|---|---|
| A — **Direct** (baseline) | Detect and localize what the training clips demonstrate | Where are the labeled events, and what distinguishes them from clean clips? | Fastest route to criteria 1–2 on look-alike videos | Unseen types, new angle, shortcut confounds; no reason to expect transfer | Yes |
| B — **Rule-first** | Which RK cash-handling requirements can be checked from video, and what does breaking each look like? | Which clauses state visible obligations and prohibitions, and what are their observable predicates? | Criterion 4; anticipates unseen types; covers omissions as "required visible step absent" | Catalog may not match what was staged; norms may be too abstract; the research effort is open-ended | Yes |
| C′ — **Mechanism discovery from staged instances** *(replaces C)* | What generalizable mechanisms do the staged clips instantiate? | Can each labeled clip be explained by a scene-independent mechanism (§4.2 test), and how many distinct mechanisms are there? | Criteria 1–2 on similar test videos; grounds B's catalog in what the organizers actually staged; labels supply impropriety for staged mechanisms (§4.3, source ii) | Bounded by what was staged. Its value for criterion 3 depends on the unknown type-judging method (§4.1, item 2) | Yes |
| ~~C — scenario memorization~~ | *Rejected as framed in revision 1*: "reverse-engineer the staged scenario set" conflates mechanisms with staging | — | Its valid core — the staged mechanisms are the best available evidence of what the organizers consider violations — lives on in C′ | Fails §4.2 tests by construction | — |
| D — **Conformance** | What does a correct operation require that can be seen? A violation is a visible departure from it | Is "normal" consistent enough across clips and angles to define departures? | Only framing with a story for unseen types beyond any catalog; fits omissions | Highest false-positive risk; departures are hard to name; a "normal" learned from a few staged clips may be just as staged. **Reduces to B's obligation half** if "normal" comes from the norms instead of the data | Yes |

**Structural observation:** B and C′ approach the same object, a **catalog of observable violation mechanisms**, from opposite ends: B top-down from law, C′ bottom-up from data. FAQ 32 guarantees they intersect on the dataset's violations. What's unknown is how much lies **outside** the intersection:
- **B \ C′**: rules that are visible but weren't staged. These are the candidates for "unseen types" (FAQ 9).
- **C′ \ B**: staged mechanisms with no clause found yet. These must still be detected (§4.3).

D's distinct contribution is departures that fit no catalog entry at all. Such a departure has, by construction, neither source (i) nor source (ii) for impropriety (§4.3). It is **an unusual action, not a detected violation**. At most it supports a hint for human review, which the binary verdict and §7 don't obviously accommodate. Whether it adds anything beyond the catalog is an open question, not a capability.

### 5.1 Unseen types and angle change: honest capability per framing

| Framing | Unseen violation types | New angle: definition transfer | New angle: recognition transfer |
|---|---|---|---|
| A | No mechanism for it | None: no explicit definition | Unknown; untested |
| B | Only as far as the catalog anticipates. Coverage is bounded and can be measured (how many rules are visible but unstaged) | Possible per rule. Relational predicates (two roles present, an object moved between them) carry over; positional ones (on the left side of the desk) don't. Zone meaning must be re-established for every scene | Unknown; untested |
| C′ | No, beyond the discovered set | Possible for mechanisms that pass the §4.2 test | Unknown; untested. Passing §4.2 doesn't imply it |
| D | Departures only, not violations (§5, D note) | Only if "normal" is defined from the norms, not learned from one angle | Unknown; untested |

**No framing has evidence of recognition transfer**, because no footage from another angle exists yet. The table separates what can be argued on paper (definitions) from what needs footage (recognition). It doesn't rank the framings on robustness.

**No framing guarantees coverage of unseen types.** The defensible target is a **bounded, declared catalog**: everything outside it is a stated limitation, delivered as part of §8 of the brief, not a hidden failure. A new angle threatens both **perception** (occlusion, scale, what is visible) and **interpretation** (roles, zones, "absent" vs. off-frame). Which dominates is unknown.

## 6. Comparison and decision gate

### 6.1 Current lean (a working hypothesis, not established)

**Lean: the mechanism catalog where B and C′ meet.** Discover mechanisms bottom-up (C′), ground them top-down (B), and extend with visible-but-unstaged rules from B, so long as their observable predicates are clear. Action confidence, impropriety confidence and citation are kept as separate claims (§4.3). A violation is claimed only when impropriety has a source, (i) or (ii).
**Strongest competitor: B-led.** The rule catalog is primary and the dataset only validates it. It is favoured if staged clips are few, unique, or confounded.
**D stays alive** as the obligation half of B (omissions), and as an open hypothesis about catalog-free departures.
**A** is the baseline every other framing has to beat.

Why the lean moved away from revision 1's "C constrained by B":
- C was optimized for the most uncertain scoring element: the type-judging method, whose existence as a fixed list is itself unverified.
- The "only if cited" constraint conflicted with recall for detections whose impropriety is otherwise supported.
- Scenario-level discovery can't be told apart from memorization without the §4.2 test.

### 6.2 Explicit decision criteria

| Evidence (observable) | Favours | Against |
|---|---|---|
| Few distinct mechanisms, each recurring across several clips with different actors or timing, all passing the §4.2 test | C′-led lean | B-led |
| Most clips are one-off scenarios, or definitions keep needing scene-specific details | B-led | C′ |
| Violation/clean clips separable by confounds (duration, actors, people count) | B-led; extra caution on anything learned from labels | A, C′ |
| Organizers confirm a fixed reference list with exact or near-exact matching (mechanism (a), §4.1) | Investing in naming that mirrors the staging | — |
| Organizers describe any other mechanism, or don't answer | Self-defensible types: what was seen + which rule (B) | Effort on guessing hidden names |
| A large share of labeled violations are omissions | B's obligation half / D | Prohibition-only catalog |
| Several staged mechanisms have no locatable RK clause after targeted search | Keep detecting them (impropriety source ii) and report the citation gap honestly | Any "only if cited" rule; **also against** extending the same tolerance to unlabelled, uncited behaviours |
| Mechanisms' key predicates are relational (roles, objects, order), not positional | Definitions carry over (§4.2, question 1). **Says nothing about recognition** | Treating this as evidence of angle robustness |
| Key predicates are tied to image regions or this desk's layout | Raising robustness to a primary concern in exploration | Treating angle as secondary |
| Own footage from another angle (E7b): a person can still judge each mechanism's predicates; the cues they use are named | Recognition transfer is plausible for those mechanisms | — |
| Own other-angle footage: key cues (roles, cash, zone) become ambiguous even to a person | Recognition is the binding robustness constraint; scope the catalog to what stays perceivable | Any robustness claim based on definitions |
| Clean clips contain near-miss behaviour (hard negatives) | Treating FP control as first-class (§6.3) | Treating FP as rare |

### 6.3 False positives vs. false negatives, without an invented cost function

What the brief does say:
- The verdict is scored per video (FAQ 15).
- "A miss is unacceptable; false positives as few as possible" (FAQ 16).
- There are only two verdicts, and leaning on "insufficient data" without justification is penalised (FAQ 15).

**Readings, without choosing a cost function:**
- **Lexicographic (most literal reading):** first, no missed violation videos; then, among options that achieve that, as few false positives as possible. It implies a violation is reported, with hedged wording, when action confidence is supported **and** impropriety has a source (§4.3). It does **not** imply reporting unusual actions whose impropriety is unsupported. That would satisfy recall by breaking §5/§7.
- **Weighted:** both count, with recall weighted more. The brief gives no weight, so don't make one up. Any operating point picked on training data inherits the training balance, which is unknown relative to the test balance.

**Structural facts that matter more than a ratio:**
- With about 5 test videos, every individual verdict matters (§3).
- Within a violation video, an extra false event can't flip the verdict, though it may cost under criteria 2–3 (unknown). On a clean video, one false event flips the verdict. **The cost of a false positive therefore depends on whether the video is clean.**
- Operationally (§3.1), the cost of a false positive is the reviewer's time to dismiss it. A flag whose evidence frame makes rejection quick costs less than one that needs rewatching. That's a property of the problem, not a scoring term.
- §7 forbids claims that rest on invisible data. Some potential false positives are therefore excluded by requirement, not by choice of threshold.

**Open:** where does an ambiguous-but-plausible event fall under the lexicographic reading, and does the training data contain enough such cases to tell?

### 6.4 Highest-impact uncertainties and the cheapest experiments

Ranked by (impact on direction) ÷ (cost). Footage cost is measured: 21.7 min of unique footage (§2.1).

| # | Uncertainty | Impact | Cheapest resolution | Pass/fail signal |
|---|---|---|---|---|
| E1 | How `type` is matched; how multi-event videos and extra events are scored; test class balance | Direction-changing (C′ naming effort, how many events to report, FP stance) | **One message to the organizers** | Their answer; no answer keeps the branches in §6.2 |
| E2 | How many distinct mechanisms the dataset holds and how often each recurs | Direction-changing (C′- vs. B-led) | **People watch every clip and tabulate:** label time, what is visible at it, a candidate mechanism, roles and objects involved. One pass covers E2–E5. Split 4 ways it's about 5–6 min of footage each, plus a joint review of disagreements | A mechanism recurs across ≥2 clips with different staging and passes the §4.2 test; otherwise it's a one-off |
| E3 | Shortcut confounds between violation and clean clips | Direction-changing (trust in anything learned from labels) | **Duration: done.** It is a moderate confound (§2.1). Still to check in the same pass: people count, actors, clothing, lighting | Any attribute that separates the labels on its own is a confound |
| E4 | Label timecode convention (onset, peak, completion; omissions) | Direction-changing (localization) | **Granularity: done** (1 s integers, §2.1). Same pass: note where the label sits relative to the visible action, and whether "the Nth second" means N.0 or [N−1, N) | A consistent offset pattern, or not |
| E4b | Х-4 ≡ Х-47 labelled at 57 s and 68 s: two violations, or label noise? | Direction-changing (multi-event reporting, label trust) | A person watches both moments of that one file (~1 min) | Two distinct visible events support multi-event reporting; otherwise treat label times as approximate |
| E5 | Share of omission violations; hard negatives in clean clips | Direction-changing (D's role, FP stance) | Same pass | Counts |
| E6 | Clause coverage for each discovered mechanism; scope of applicable acts | Direction-changing (criterion 4, C′ \ B gap) | Targeted adilet.zan.kz / НБРК search per mechanism, capped in time | Mechanisms with a located clause vs. without; the act's scope matches bank cash operations |
| E7a | **Definition** transfer: is each mechanism's definition viewpoint-independent? | Direction-changing (which mechanisms are even candidates for robustness) | Paper exercise: write each mechanism's predicates and mark which are relational and which positional | Share of positional predicates |
| E7b | **Recognition** transfer: can a mechanism's predicates still be perceived from another angle? | Direction-changing; the **only** evidence on robustness beyond definitions | Re-stage a few scenarios (violation and clean) from a different angle with a phone (FAQ 7 allows own footage). A person judges each one from the new view alone, before seeing the overhead view, and records which cues they relied on | Per mechanism: judgeable or ambiguous for a person, plus the named cues. Without this footage, recognition transfer stays **untested** and must be reported that way |
| E8 | Visible-but-unstaged rules (B \ C′) | Direction-changing (unseen-type coverage) | Part of E6: list visible clauses that no clip exercises | Count and clarity of their predicates |
| E9 | Compute and hosting for 5 min/video | Direction-changing (scope) | Ask the team | Confirmed resources |

E1 and E9 cost a message each. E2–E5 is a single pass over the footage. E6–E8 are bounded desk research. None of these needs anything built.

### 6.5 Team and time constraints (4 people, 24 h, heavy AI use)

- **The bottleneck moves away from writing code.** With AI-assisted development, the scarce resources are human judgment on the footage (E2–E5), human verification of every clause (E6), and end-to-end checks on the real public deployment within 5 minutes per video. Framings that need a lot of human evidence work cost more than they appear to.
  - **B-led:** open-ended legal reading.
  - **C′:** careful mechanism tests.
- **Parallelism changes the cost of exploration, not of decisions.** E2–E5, E6–E8, E1/E9 and setting up the required deliverables can run at once. The C′-led vs. B-led choice still depends on E2/E3 and should fall **early**, not after work has piled up on one branch. AGENTS.md also asks for the main flow to stay runnable throughout development.
- **Where AI help applies:**
  - Used for: development and coding (the team's plan); research on *public* legal texts is also fine.
  - Not used for: dataset video or frames (§7 guardrail).
  - Needs human checking: AI-proposed citations, mechanism definitions (AI is prone to memorization-style ones, so apply the §4.2 test), and claims about the act's scope.
- **The 24 h limit favours a declared, bounded catalog (§5.1) over open-ended coverage.** That is now a feasibility reason, on top of the honesty reason.
- **Still unknown:** compute and hosting (E9). It decides the analysis depth possible within 5 min/video, and whether the public URL is reachable throughout judging.

## 7. Exploration handoff

- **Original challenge preserved:** §1 must-haves unchanged.
- **Non-negotiables:** UI plus the exact two-step API and JSON schema; `X-API-Key`; binary verdict only; 1–3 JPEG base64 frames; under 5 min per ~29 MB `.mov`; fully local, offline after weights load; no cloud AI, faces, or audio; commercially licensed open-source only; RK sources only, no invented clauses; no claims that need invisible data; the output is a hint, not a finding.
- **Working hypothesis:** a mechanism catalog where B and C′ meet. Action confidence, impropriety confidence and citation are separate claims, and a violation is claimed only when impropriety has a source (§4.3). **Competitors kept open:** B-led; D as obligations / catalog-free departures; A as baseline.
- **Success criteria:** correct per-video verdict with recall first and FP minimized after that; a timecode and frame that show the event; a type that is defensible on its own (what was seen + which rule), whatever the undisclosed judging method; citations that check out, with stated interpretation; no violation claimed without a source for impropriety; mechanism definitions that pass §4.2, with recognition transfer shown on other-angle footage or declared untested; reliable completion within the time budget; declared catalog limits.
- **Unresolved branches:** E1 (matching and scoring), E2/E3 (mechanism recurrence vs. confounds), E5 (omissions), E7 (viewpoint dependence), E9 (compute).

**Hypotheses to test in `/problem-explore`** (each falsifiable by E1–E8):
- H1: The staged violations reduce to a small set of scene-independent mechanisms (E2).
- H2: Violation and clean clips are not separable by non-violation attributes (E3).
- H3a: Most mechanisms' *definitions* are relational, not positional (E7a).
- H3b: For those mechanisms, the predicates can still be *perceived* from a different angle, at least by a person (E7b). H3a being true doesn't make H3b true.
- H4: Every discovered mechanism has a locatable RK clause whose scope covers bank cash operations (E6). If false, the C′ \ B gap is real and must be reported.
- H5: There are visible RK requirements that no training clip exercises, and they are plausible test types (E8).
- H6: Label timecodes follow one consistent convention, including for omissions (E4).
- H7: `type` is judged against a fixed reference list (§4.1, mechanism (a)). Only a working hypothesis among (a)–(e); E1 tests it. Until then, nothing depends on H7 being true.
- H8: Every labelled training mechanism has a source for impropriety beyond "it looked unusual": a clause, or at least the label itself (E2, E6).

**Questions for `/problem-explore`:**
1. For each mechanism, which observation → interpretation → judgment steps are reliable, and which rest on assumptions (roles without faces, object identity, zone meaning, absence vs. off-frame)?
2. What visible evidence separates a confident event from an ambiguous one, given one verdict bit and FAQ 16's ordering?
3. How should an omission be anchored in time to match the label convention, and what must be visible to claim it at all?
4. What would let a reviewer dismiss a false positive quickly, as the operational FP cost (§3.1)?
5. What is the declared catalog boundary, and how is it communicated as a limitation?

## 8. Revision log

- **Rev 5** (team review):
  - Split angle robustness into definition transfer vs. recognition transfer (§4.2, §5.1, §6.2). Robustness claims no longer rest on definitions, and E7 is split into E7a/E7b, with H3 split to match.
  - Split a violation claim into action confidence, impropriety confidence and citation (§4.3). An unusual action isn't a violation, and the "decoupling" is narrowed to detections whose impropriety has a source. D's departures are relabelled as hints, not violations; added H8.
  - Downgraded the "hidden type list" from inference to one of five possible judging mechanisms (§4.1, H7).
- **Rev 4:** dataset arrived. Added §2.1 with measured facts: 40 unique videos (2 duplicate pairs), balanced labels, 1 s label resolution, a moderate duration confound, and the Х-4/Х-47 double-label. E3/E4 partly resolved; added E4b. Framings and lean unchanged; the duration confound adds weight to the §6.2 "confounds" row.
- **Rev 3:** added team constraints (4 people, 24 h, AI for coding only), the §7 guardrail (dataset video stays out of cloud tools), the risk of AI-invented legal citations, and §6.5. Framings and the lean are unchanged.
- **Rev 2:**
  - Replaced C (scenario discovery) with C′ (mechanism discovery) and added the memorization test (§4.2).
  - Added the observation / interpretation / judgment layering (§4.3).
  - Withdrew the "only if cited" constraint, which conflicted with recall.
  - Corrected the claim that false positives are the main way to lose verdict points.
  - Added the small-sample arithmetic, the proxy vs. operational table (§3.1), explicit decision criteria (§6.2), the FP/FN analysis without a cost function (§6.3), and a ranked experiment table (§6.4).
- **Rev 1:** initial reframing; an adversarial pass added the per-event scoring and face detection vs. identification items.
