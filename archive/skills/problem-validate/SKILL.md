---
name: problem-validate
description: Falsify, reproduce, and experimentally compare hackathon solution candidates; assess trade-offs, competitive value, and decision stability before implementation. Use after problem-explore, or when technical claims, benchmarks, and competing solution directions need independent validation.
---

# Validate and Select a Hackathon Solution

**Goal:** Choose the strongest feasible direction for this competition, not merely the safest, simplest, or most elaborate. Read the original brief and `problem-reframing.md` / `problem-exploration.md` when available. Treat missing constraints as unknown, not as permission to invent them.

## Rules

- Preserve every mandatory requirement. Compare optional mechanisms **on top of a compliant baseline**, never as replacements. A mandatory AI feature does not become optional because its added user benefit has not been measured.
- Label claims **verified observation**, **reasoned estimate**, **reported but unreproduced**, or **untested hypothesis**. LLM judgment can justify a provisional choice, not an empirical claim. Do not fabricate measurements or numeric rankings.
- Prioritize **decision-relevant evidence**. Specify falsifiers and discriminating tests before inspecting results. Run feasible, safe checks; preserve scripts, commands, fixtures, logs, and environment in `validation-evidence/`. Do not modify product code, original briefs, or source datasets for validation.
- Distinguish computational correctness, user benefit, judging advantage, and end-to-end delivery feasibility. Evidence for one does not prove the others.

## Workflow

1. **Frame the choice.** Extract judge weights, must-haves, baseline, available time, team capabilities, and demo constraints. Inventory **all materially distinct promising candidates** from exploration, including useful combinations. Screen for compliance and plausible relevance; only then shortlist 2–3 finalists plus the compliant baseline. Record why any serious contender was excluded.
2. **Register pivotal claims.** For each finalist, state its unique advantage over its strongest rival, what would falsify it, evidence status, and the consequence if false. Include feasibility claims and catastrophic failure cases.
3. **Predefine discriminating experiments.** Ask *what result would favor A over B?* Use matched inputs, independent oracles, representative and adversarial cases, confounders, and stopping conditions. Select the cheapest test likely to change the choice. Separate deterministic checks from noisy measurements; use `experiment-guide.md` when needed. Do not invent numeric thresholds.
4. **Execute and reproduce.** Run safe, inexpensive tests, retaining reproducible evidence in `validation-evidence/`. Recompute pivotal counts, optima, timings, and invariants from primary inputs. Distinguish planned, executed, and blocked experiments. If a comparison requires unavailable readers, endpoints, or demo hardware, record the unresolved claim instead of favoring the easier-to-measure option.
5. **Delegate selectively.** Give `independent-verifier` **one bounded claim** to check from raw inputs and `adversarial-evaluator` the brief and evidence to find counterexamples, unmet requirements, and missed high-value approaches. Give the challenger the original brief before the preferred choice when possible. If subagents are unavailable, perform direct checks and disclose the independence limit. Agents' opinions alone do not verify claims.
6. **Analyze quality trade-offs (ATAM-lite).** For each serious contender or hybrid, examine 2–4 priority scenarios: **stimulus → conditions → observable response**. Identify risks, supported non-risks, sensitivity points, and trade-off points. Do not claim to have performed a full ATAM.
7. **Compare competitive value and opportunity cost.** Relative to the compliant baseline, compare observed gains, judging relevance, possible user value, implementation/integration effort, demo risk, reversibility, and consequential unknowns. Estimate delivery effort from known team/time constraints; if unknown, define a minimum viable scope and label estimates conditional. Do not select solely for simplicity or closeness to the initial framing. Compare the strongest rejected candidate and the best feasible hybrid under **the same** criteria.
8. **Check decision stability.** Identify which evidence, assumptions, and priorities determine the ranking. Test whether plausible changes in time, team capability, or demo requirements reverse it. When a previous ADR exists, explain any change using **new evidence, changed constraints, or judgment-dependent trade-offs**. If evidence cannot distinguish candidates, say so; preserve switching conditions rather than inventing certainty.
9. **Decide and stop.** Run one more affordable experiment only if it might reverse the selection and is worth the time. Otherwise choose `build`, `build conditionally`, or `defer`. State the best feasible direction/combination, implementation priorities, fallback, and acceptance checks. Stop when further research has low decision value relative to the hackathon budget.

## Deliverables

- **`problem-validation.md`:** Compliant baseline; screened candidates and rationale; claim/falsifier/evidence register; planned vs. executed experiments with reproducible paths; comparative evidence, costs, judging relevance, risks, hybrids, and unresolved decision-changing questions.
- **`solution-decision.md`:** Concise ADR with status; constraints; selected direction; strongest rejected option; best feasible hybrid; evidence vs. engineering judgment; opportunity cost; delivery feasibility; decision-stability/switching conditions; fallback and acceptance checks. Explain any change from a previous ADR. **No detailed implementation plan.**

## Example: «Аким на 5 часов»

Exploration reports 694,395 feasible assignments and maximum Score 57.236735. Independently reproduce these claims, but don't confuse **exact computability** with **value to users**. Compare district breakdowns, local one-step replacements, global Pareto alternatives, and grounded AI explanation (mandatory AI compliance remains separate from optional enhancements). Evaluate local, global, and hybrid choices for missed trade-offs and demo cost. If user value cannot be tested, make the choice conditional rather than declaring a proven winner.

## Quality gate

Did the tests distinguish candidates rather than merely verify arithmetic? Are key claims reproducible? Were all serious approaches screened fairly? Are optional advantages kept separate from mandatory compliance? Does the ADR explain why the choice beats its strongest rival and feasible hybrid, what would reverse it, and why any prior recommendation changed?

**Cross-run consistency audit.** When previous validation artifacts exist, compare decisive numerical claims, candidate rankings, experimental definitions, and prior decisions.

If results conflict under supposedly identical inputs and rules, reproduce the discrepancy from primary sources before relying on either result.

Distinguish genuine new evidence from changes in assumptions, methodology, or subjective judgment. Do not silently replace earlier findings.