# Owner D3-2: independent validation and rule-scope audit

Own `eval/audit_findings.py` (or narrowly named equivalent), NEW tests/test_audit_findings.py, and
`attempts/A21-deadline/validation/` only. Read but do not edit runtime, shared schemas, annotations,
knowledge YAML, global docs or other workers' files. CPU work; no GPU needed.

Build a runnable independent audit of cached replay or API output. Keep binary organizer verdict,
human-observed events and legal/policy validity separate. Deduplicate by SHA with both X4/X47
timestamps preserved, but do not let the nearest timestamp make a different reason 'correct'.
Report verdict confusion counts, known compatible event timing, supported/contradicted/unknown
reason status, missing annotation coverage, duplicate/sample counts, invalid outputs and runtime
when present. No invented overall reason-accuracy percentage. Pin exact cache paths/hashes so
mtime-dependent newest-cache choice cannot silently change the compared inputs.

Use supplied common brief observations as provenance-tagged evaluation assertions, NOT runtime
per-file rules. Baseline wrong ID reason on X4 and wrong room-exit docs reason on X20 must be
visible audit failures even when binary verdict matches. X1 cause remains unknown; no reason
score there. X43/X45 cutoffs prevent future-abandonment accusations. Key/detector-disabled rules
are capability gaps. Expose provisional ID policy rather than treating clean X19 as proof ID is
unnecessary. Report other assumptions without inventing authoritative ground truth.

Add meaningful fixture tests (correct verdict/wrong reason, duplicate timestamps, unknown cause,
missing predictions, invalid records). Audit current baseline from existing repo A20 logs if no
cache accessible. Provide exact CLI and artifact. First auditable baseline within25min. Include
a short prioritized inventory of unsupported rule assumptions for orchestrator source review.
