# A22 context worker

2026-10-18 04:26 UTC: reading the supplied combined A22 base (not the dirty A21
worktree). The archive became available during the first read; no current blocker.
No separate trace.py exists: the current trace implementation is
backend/f1/detector.py:build_trace. Read events.py, visual_checks.py and vision_types.py.

Scope: one bounded build_llm_context function, a small numeric fixture test file,
one real-cache/trace CPU smoke, and an unapplied minimal visual_checks.py call-site
patch for parent review. No runtime, verdict, law, model, config or service changes.

Interface: preserve supplied fixture facts if present; geometric near-hand/safe
relations remain proxies, never proven possession, ownership or active handling.
No fixture_evidence implementation exists in the supplied base yet. Full context
is diagnostic; the proposed visible-state prompt receives geometry/coverage only,
with the image primary. Exact actual prompt/context must enter the request/cache key.

2026-10-18 04:33 UTC: ready for parent review. Public API implemented and checked
against an isolated copy of the supplied combined base. Four numeric fixtures
passed in0.15s; one real numeric-cache trace smoke passed. Final context15925B,
14.238ms; actual geometry/timing-only prompt payload1465B. Exact argv, source/cache
hashes, context and trace artifacts are in this directory. Classifier predictions,
roles and event names stay in diagnostics, not the visible-state prompt.

candidate.patch includes the minimal proposed shared call-site change; it passes
dry-run against supplied A22 base. The actual request/context/prompt are covered
by cache identity and prompt hash. No edits to shared files or live service, no
GPU work and no dependency/config/rule/verdict changes. D2-2 fixture facts are
preserved when supplied, without an independent active-use classifier.

Measured limits: same track has outsider/cashier role values; global scene
confidence1.0 coexists with low fixture scores. These remain explicit uncertain
CV inputs rather than new truth. Serialization alone is not an accuracy result.
Initial lint and a prompt-projection smoke failure were corrected. No blockers.
