# Claude Opus 5.5 review: ID-rule evidence

## Consultation record

The user explicitly approved the exact prepared text-only packet after automatic approval review
required separate consent for the new payload. The consultation then succeeded. The response
reported **`claude-opus-5-5`**, invoked with **`--effort high`**. Tools and MCP were disabled,
safe mode was enabled, and no session was persisted. Input was the approved anonymized evidence
problem, with no source files, clip identifiers, videos, frames or credentials. Byte equality and
the packet SHA-256 were checked before submission and when preserving the response.

- Review latency: 27.2 s; this is not detector runtime.
- [Verified invocation metadata](../logs/opus-5-5-id-rule-review-metadata.json).
- Raw prompt, response and metadata: `runtime/consultations/datathon26-opus55-rule-evidence-review-20261018T022552Z/` (gitignored).
- Packet SHA-256: `788785f696cc35fb95a42b71ecb04617619ffcfb2de104cf2c297536e1a0ce64`.

## Checked conclusions

1. **ID-first remains provisional and unverified in scope.** Sultanbek's X-19 correction and the
   organizer's clean label are retained separately. They challenge the blanket visual rule without
   establishing that identification is never required. The earlier user assertion was retracted.
2. **Current runtime is unchanged.** X-19 currently emits no finding. The review's literal-rule
   contradiction is conditional on correct cash/session evidence reaching the evaluator; it is
   not an observed X-19 false positive. The canonical rule remains enabled/business-confirmed,
   and its citations remain pending in [the rulebook](../../../knowledge/rulebook.yaml).
3. **Separate recognition, session association, coverage and policy applicability.** A missing
   ID event can arise at several pipeline stages. Keep observed presentation, reported absence
   with adequate visibility, and insufficient visibility distinct. This does not retract the
   human observation or justify borrowing another client's ID.
4. **Reason review remains possible without a reason-accuracy percentage.** In X-4/X-47 the
   human descriptions directly contradict the missing-ID explanation. That can be recorded as
   an evidence error without asserting a legally verified cash-mixing rule. No complete reason
   ground truth exists, so no overall reason-accuracy metric is claimed.
5. **No per-file fixes or relabeling.** Policy verification and observability should govern all
   applicable sessions, independently of filenames, organizer outcomes and expected object order.

Later annotation update, after this consultation: the user confirms physical cash stacking in
X-4. The initially ambiguous wording "ID after money" was immediately clarified by the user as
"ID first, then money", consistent with the original description. Conclusion 4's evidence
contradiction therefore remains supported. The original response below is preserved unchanged;
the later entry/stacking observations are recorded separately in the annotation audit.

The [task FAQ](../../../task.md) confirms that labels provide verdict/time and no violation type.
Opus's suggestion to ask the organizer whether X-19's clean label evaluated ID ordering is a
useful clarification draft. No message has been sent to the organizer. This text-only consultation
provides advice, no new model measurements, legal verification or implementation authorization.

## Original response (verbatim; qualifications above apply)

# Design Review: ID-First Rule Evidence

## Overreach

Most conclusions hold. Four need tightening:

1. **"Disputed" says too much.** The rule is *unverified*. Its citations are pending, and one organizer verdict conflicts with it. Nothing argues the rule is false, so "provisional, unverified" is more accurate.
2. **The clean label is not an explanation.** Don't record the clip as "ID not required here." Organizer labels give a verdict and a time, not a reason.
3. **"Reason-correct" cannot be scored yet.** No authoritative reason labels exist. The "cash-mixing" concern in the positive case is a description, not verified ground truth. Treat reason-correctness as a review criterion, not a metric.
4. **"Observed non-presentation" needs a visibility condition.** The human's observation in the clean clip may still miss off-camera or occluded presentation. Use three states: presented-observed, absent-with-adequate-view, and unobservable.

## What the clean counterexample establishes

- One organizer-clean verdict coexists with a human-observed cash-before-ID sequence for the first visitor.
- The implemented rule, applied literally, would contradict that verdict.
- So the blanket rule cannot be held as project truth against the current labels.

## What it does not establish

- That ID is unnecessary, or that any legal exception exists.
- That the organizer evaluated ID ordering at all.
- That the human observation is complete.
- How "client session" should be bounded (for example, whether the two visitors form one session).
- Anything beyond this one clip.

## Smallest next evidence check

Ask the organizer one yes/no question about the clean clip: *"Did the clean verdict consider whether ID was shown before the first visitor's cash transfer?"*

This needs no timestamps, no annotator work and no broad review. It also separates two cases: "the label covered ordering" versus "the label is silent on ordering."

## Advisory recommendations (not measured)

- Keep the original labels and the human correction verbatim, with provenance.
- Keep the card detector independent of rule expectations.
- Avoid per-file exceptions.
- Leave production enable flags unchanged during the interview.
- Track citation and scope verification as an open item.

## Measured or observed (not verified)

- **Pipeline output:** the system emitted a missing-ID finding on the positive clip. This is the only system output reported.
- **Human observation:** both visitors showed ID before cash in that clip. This implies a card-detection miss. The verdict matches the label, but the stated reason is wrong.
- **Organizer labels:** binary verdicts. They do not certify every visible action.
- **Not available:** no detection rates or legal determinations.
