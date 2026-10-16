---
name: problem-reframe
description: Reframe hackathon briefs and technical challenges into testable, competition-aligned problems before solution design. Use for challenge statements, judging briefs, optimization tasks, or suspiciously obvious solutions; identify assumptions, critical uncertainties, and exploration priorities.
---

# Reframe a Hackathon Problem

Find the problem worth investigating, not an impressive-sounding solution. Preserve mandatory requirements while questioning assumptions and the unit of analysis.

## Boundary

Do **not** recommend features, algorithms, models, stacks, or architectures. Conceptual distinctions (e.g., per-tool vs. per-invocation risk) are allowed; solution design belongs to `/problem-explore`. If a full pipeline is requested, return the handoff without asking permission to continue.

## Workflow

1. **Extract the brief.** Restate the challenge; separate explicit facts, inferences, and unknowns. Capture must-haves, judging weights, data, time, restrictions, and demo conditions when provided. Never reframe away a mandatory deliverable.
2. **Find the objective.** Distinguish the requested artifact from the desired outcome. Choose relevant lenses: human/product, technical performance, operational/security, scientific/analytical, or business. Identify tensions between outcomes and scoring proxies.
3. **Challenge the framing.** Ask whether the task targets a symptom, cause, or proxy; whether its unit of analysis is appropriate; and which assumption, if false, changes the problem. Label challenges **supported**, **unverified**, or **incompatible with requirements**.
4. **Map evidence and measurement.** Tag constraints **explicit / likely / unknown** and assumptions **stated / inferred / unverified**. Identify outcome and proxy metrics, justified baselines, and judging relevance. Never invent targets or scores.
5. **Generate 3–5 distinct framings.** Include a **direct**, **root-cause**, and **assumption-breaking** framing when compatible; add constraint, scope, inverse, analogy, or extreme-case lenses only if useful. Each must specify the desired change, preserve required deliverables, allow multiple solutions, and note a blind spot. Merge formulations with essentially identical research questions and success criteria.
6. **Compare conditionally.** Assess judging alignment, leverage, hackathon feasibility, demonstrability, and uncertainty. Use qualitative judgments with short reasons, not fabricated numeric rankings. Identify a provisional framing and runner-up, or specify the condition that would favor each.
7. **Triage uncertainty before handoff.** Classify open questions as:
   - **Blocking:** Progress would violate requirements or cannot meaningfully proceed without an answer.
   - **Direction-changing:** Different answers favor different framings or exploration priorities.
   - **Noncritical:** Defer without significant consequence.

   For blocking or direction-changing questions, choose the cheapest resolution: inspect supplied evidence, do targeted research if available, ask **one** high-value user question, or preserve conditional branches. Do not ask for facts already in the brief or for implementation preferences. If the user requested uninterrupted discovery, branch rather than pause unless genuinely blocked. Do not delay exploration to settle noncritical unknowns.

## Output

Save a concise `problem-reframing.md` with:

1. **Challenge and objective:** explicit requirement versus interpretation; appropriate problem type.
2. **Evidence map:** assumptions, constraints, unknowns, and why each matters (compact table).
3. **Success measures:** outcome vs. proxy, known baseline, judging relevance (no invented targets).
4. **Challenge to framing:** central questionable assumption or unit of analysis, with evidence status.
5. **Alternative framings:** 3–5 genuinely distinct formulations, opportunity, blind spot, must-have compatibility.
6. **Comparison and decision gate:** provisional first choice and runner-up; uncertainties labeled blocking / direction-changing / noncritical; the next action for each consequential unknown.
7. **Exploration handoff (short):** primary and alternate framing, non-negotiables, success criteria, unresolved conditional branches, and questions for `/problem-explore` to investigate. **Do not suggest implementations.**

Keep the report proportional to the brief. For short challenges, compress tables rather than manufacturing detail. Example: in tool-security classification, comparing **per-tool capability** and **per-invocation risk** is a reframing; choosing a classifier or runtime monitor is solution design.

## Quality gate

Before handing off, verify: facts differ from inference; must-haves remain intact; formulations differ in underlying problem rather than wording; metrics are observable; choices reflect judging and feasibility; consequential unknowns have an action or conditional branch; no architectures slipped in. If new evidence changes the framing, revise affected sections, not the entire report.

Treat the selected framing as a working hypothesis, not a final decision. Preserve at least one credible competing framing and identify what evidence could favor it.

The exploration handoff must preserve the original challenge, mandatory constraints, and competing directions. Do not restrict solution exploration to the provisional framing.

### Optional adversarial reframing
Use an independent subagent only when the brief contains conflicting objectives, ambiguous mandatory requirements, or competing framings that could materially change the direction.

Give the subagent the original brief and judging criteria before showing it the preferred framing. Ask it to independently identify overlooked objectives, questionable assumptions, alternative units of analysis, and potential requirement violations.

Compare its findings against the main analysis. Revise only when it identifies a genuinely different, supported perspective or a meaningful error. Do not add alternatives merely to increase their number.

For straightforward briefs, skip delegation and use the existing quality gate.