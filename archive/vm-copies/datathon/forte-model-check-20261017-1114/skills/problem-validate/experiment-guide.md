# Discriminating experiment guide

Use only sections needed for the decision; do not mechanically execute a catalog of methods.

## Minimal protocol (write before testing)

1. **Decision:** What competing candidates could this test reorder?
2. **Claim and falsifier:** What result would undermine a finalist's unique advantage?
3. **Oracle and inputs:** What independent source of truth or matched workload will be used? Include typical, boundary, and adversarial cases.
4. **Measurement and control:** Which metrics matter? What must stay fixed? What is uncertain or confounded?
5. **Execution:** Exact script/command, dependency versions, environment, and output location under `validation-evidence/`.
6. **Interpretation:** Observed outcome versus estimate; what selection changes, and what remains untested?

## Choose a method that fits the claim

- **Deterministic correctness:** Enumerate where tractable; assert invariants, edge cases, constraint compliance, and exact or toleranced numeric results. Statistical significance is irrelevant to exact arithmetic.
- **Performance:** Hold workload/hardware/configuration fixed; separate startup and steady-state latency; repeat measurements when noisy. Don't generalize a one-off research script's timing to production UI latency.
- **LLM quality:** Fix input facts and task; record exact model/version/prompt/settings, full outputs, hallucinations, and relevant comparisons. Use real readers for comprehension claims when possible. An LLM judging its own prose is not a user study.
- **Human-facing value:** Compare equally complete experiences on equivalent cases. Record actual task outcomes and confusion, not aesthetic preferences alone. Small convenience samples justify only provisional conclusions.
- **Resilience/security:** Exercise permitted failure and abuse cases without destructive actions. Test fallbacks and control boundaries, distinguishing a prompt instruction from enforced safeguards.

## Decision rule

Prefer tests with **high potential to change the solution choice relative to effort**. If evidence is unavailable or a test cannot distinguish candidates, preserve that uncertainty and choose provisionally with clear switching conditions. Do not let easily measurable claims crowd out strategically important but unmeasured ones.
