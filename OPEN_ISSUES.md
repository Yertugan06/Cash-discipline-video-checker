# Open issues

Current measured release: [A21](attempts/A21-deadline/RESULTS.md). Keep historical
experiments in their own folders; this list describes outstanding work.

## Detection score regressed and ten violation clips remain missed

A21 scores 30/40 (11/21 violation clips caught), against A20's 32/40. Clean false alarms
remain 0/19. Two contradicted accusations were removed without recovering the real
mechanisms in X4/X47 and X20. Findings compatible with human prose remain 9; 3 are unknown.
The enabled local VLM has not improved the score. Recover evidence for cash at client
change and safe attendance; do not reinstate wrong ID/documents accusations for the score.

## Missing or weak observations

Cash/ID localization, ownership through occlusion, fixture calibration, safe attendance,
screen readability, key-after-exit and rejected-note inspection remain weak or unimplemented.
Only safe-state VLM checks are enabled. A still-frame missing ID cannot establish a whole
non-presentation interval; blanket ID-first policy scope is unverified. X1/X2 causes are
unresolved. [Current miss list](docs/LIMITATIONS.md#current-misses-and-uncertainty).

## Legal citations are pending

There are 21 catalog rules, 15 enabled, with evaluators for all enabled IDs. No rule is
jury-eligible while its cited norms/acts await human verification. All 12 citations in the
current run are pending; `RULE_SCOPE=detector` is for review, and jury scope is gated.
See `knowledge/README.md`; detection agreement does not verify legal applicability.

## Validation and runtime coverage

All 40 public clips influenced development. A20 cached geometry perturbations are not
unseen-camera data or a full robustness validation of every A21 change. The longest-clip
cold run with the current VLM enabled is unmeasured. The 2.0675 s median is predominantly
cached work. Under an upload burst, jobs now share time and drop to 1 or 0.5 fps;
accuracy at those rates and a real burst on the L4 are unmeasured.

## Deployment and documentation boundaries

The validated A21 review service is on datathon2 (8003/8103); the former 8002/8102 preview
is stopped. The public A20 endpoint on datathon was not replaced. A push alone does not
move model weights or runtime annotations/results. Startup/data paths and current evidence
are documented in `realtime/README.md` and the A21 release report.

`docs/RULES.md` is generated from catalog metadata; enabled is not proof that a rule's
required observations are produced reliably. Archive/research documents and attempt logs
remain historical. Their original results are not silently rewritten to match current code.
