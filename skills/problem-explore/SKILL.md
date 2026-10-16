---
name: problem-explore
description: Investigate solution spaces for hackathon challenges after problem reframing. Use when a brief or problem-reframing.md exists and the team needs evidence-backed, non-obvious solution approaches before architecture selection. Coordinates independent research subagents, contradiction analysis, feasibility checks, and selective deepening.
---

# Explore Hackathon Solutions

## Goal and boundary
Discover **different, defensible solution mechanisms**, not a list of attractive features. Use the original brief and `problem-reframing.md` if present; the provisional framing is a hypothesis, not a mandate. Preserve must-haves, judging criteria, and competing framings. Do not start product implementation or finalize architecture in this skill. Exploratory calculations, tiny throwaway scripts, and literature/code searches are allowed.

## Process

1. **Set the search question.** Restate the required outcome, immutable rules, evaluation criteria, known resources, and top uncertainties. Define what a better solution would demonstrably improve. Separate objective evidence from speculation. If the brief is missing, work from available information and label gaps.
2. **Partition exploration by hypotheses, not personas.** Identify 3 substantially different research directions suited to the challenge (e.g., exact optimization, explainable decision support, and robust decision-making). For trivial or narrowly specified tasks, use fewer. Delegate each direction to an independent `solution-investigator` subagent (parallel when available). Give each the same brief, constraints, and evaluation questions but **not** other agents' candidate conclusions. Read `investigation-brief.md` for the task template.
3. **Demand investigation.** Each investigator must: search credible existing methods when tools permit; construct an explicit mechanism; inspect applicable constraints; perform a bounded calculation or feasibility check where possible; identify a surprising insight or report none; and cite sources or mark claims unverified. Return concise findings, not a brainstorm dump. If delegation or browsing is unavailable, perform these investigations sequentially and label evidence limitations.
4. **Synthesize the design space.** Build a small morphological map of meaningful independent dimensions; use it to identify missed combinations. Consolidate overlapping ideas into 4–6 genuinely different candidate families **when the problem supports that many**. Include a simple compliant baseline. Reject impossible candidates with precise reasons; do not pretend different UI variants are different architectures.
5. **Resolve important contradictions.** Find up to two consequential trade-offs. Use relevant TRIZ principles (not all 40) to derive testable mechanisms that could change the trade-off. Explain why each principle applies and what new cost or risk it introduces. Skip TRIZ when no real contradiction exists.
6. **Challenge and deepen.** Select 2–3 candidates based on evidence, judging alignment, potential advantage, and feasibility. Delegate a `solution-critic` subagent to attack the claims and search for missing approaches, especially the baseline or an unexamined simpler solution. Reopen a rejected branch if the critique overturns an assumption. Do **one targeted follow-up investigation** for the highest-value unresolved issue, if useful. Do not make agents endlessly debate.
7. **Handoff.** Produce `problem-exploration.md` with: objective and constraints; research findings with provenance; morphological map; candidates and unique mechanisms; contradiction/resolution; discarded alternatives; 2–3 finalists plus baseline; uncertainty and evidence table; **cheapest discriminating experiments** with measurable pass/fail signals; recommended next experiment and conditions that would change the ranking. Do not turn untested predictions into results.

## Evidence and stopping rules
- Prefer calculations, executable probes, official docs, papers, and verified examples over agent consensus. LLM votes/ratings are not empirical evidence. Do not invent speed, accuracy, originality, or judging scores.
- Source claims should include URLs or file references; distinguish *measured*, *derived*, *documented*, and *hypothesized* claims.
- Require genuine differences in underlying mechanism, not wording. If agents converge, ask what assumption or dimension remains unexamined before generating more variations.
- Stop when added exploration is unlikely to change the finalists or when its cost threatens a credible hackathon implementation. Explicitly record what remains unknown.
- If results contradict mandatory rules, reject or label as optional; never replace the required deliverable.
- When new evidence overturns a key assumption, revise the affected comparison and experiment plan rather than rewriting everything.

## Example
For a 14-measure, exactly-five-measure city simulator, investigate **(a)** exhaustive feasible-scenario search, **(b)** traceable scoring explanations, and **(c)** robustness to synthetic assumptions. Don't settle for “basic app vs app with charts.” Compute or bound the scenario count before claiming search is practical; test whether all proposed explanations agree with the deterministic score; preserve the official scoring rules.
