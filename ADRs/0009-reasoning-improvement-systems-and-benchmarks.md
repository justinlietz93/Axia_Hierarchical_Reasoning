# ADR-0009: Reasoning Improvement Systems And Benchmarks

## Status

Accepted

## Context

Axia is not merely a wrapper around model calls. Its value depends on improving small-model reasoning through explicit systems: decomposition, context assembly, typed intermediate artifacts, validation, scoring, repair, verification, synthesis, and replay.

The project should not measure success only by whether a run completes. It must show that the orchestration improves results over a single-shot baseline and that the improvement comes from inspectable reasoning controls.

## Decision

Axia admits reasoning-improvement systems as a first-class feature group.

The MVP must prioritize:

- canonical request formation;
- task constitution formation;
- typed work graph formation;
- schema-constrained model outputs;
- deterministic validation;
- scorecards and verifier-style checks;
- bounded critique, repair, and regeneration;
- selective context packing with provenance;
- final synthesis from accepted artifacts only;
- replayable traces;
- a benchmark comparing single-shot output, quick mode, and standard mode.

Advanced strategies such as self-consistency, verifier-guided selection, branch search, and multi-branch synthesis may be admitted later only when they remain bounded and produce inspectable artifacts.

## Evidence

- The README frames Axia as a reasoning-improvement system around small local models.
- `docs/SPEC-1.md` requires reasoning decomposition, critique, repair, synthesis, structured traces, and bounded loops.
- `docs/axia_spec.md` requires a reasoning-improvement benchmark against a single-shot baseline.
- `ARCHITECTURE_STANDARDS.md` requires final synthesis from accepted artifacts and bounded recursive reasoning.

## Invariants Involved

- Axia must improve reasoning through explicit, inspectable controls.
- Every accepted artifact must be validated before use.
- Every refinement loop must be bounded.
- Final answers must be synthesized from accepted artifacts.
- Reasoning improvement must be measurable against a baseline.

## Alternatives Rejected

### Treat orchestration completion as success

Rejected because a completed run can still be worse than a single model call. Axia must measure reasoning improvement, not just workflow execution.

### Add heavy branch search before a simple graph is proven

Rejected because unmeasured test-time compute can hide failure, increase latency, and make the system harder to inspect.

### Rely on free-form chain-of-thought as the improvement mechanism

Rejected because Axia should prefer artifact-level reasoning with typed contracts, validation, scorecards, and replayable traces.

## Consequences

Axia's first useful implementation must include benchmarkable reasoning controls. This increases early implementation scope slightly, but it prevents the project from becoming a generic agent runner with no proof of uplift.

## Review Trigger

Review this decision if benchmark evidence shows that a different reasoning-improvement strategy should become the default graph or if advanced branch/search methods outperform the standard graph without harming inspectability.

