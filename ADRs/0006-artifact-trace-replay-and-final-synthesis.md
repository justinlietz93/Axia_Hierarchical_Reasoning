# ADR-0006: Artifact Trace, Replay, And Final Synthesis

## Status

Accepted

## Context

Axia's final answer should be auditable. The user should be able to inspect how the answer was produced without depending on hidden free-form chain-of-thought. The controller must also be debuggable and replayable.

## Decision

Axia admits artifact-based final synthesis, run trace projection, and replayable manifests as core features.

The final synthesizer receives accepted artifacts, scorecards, unresolved caveats, requested format, and the task constitution. It must not invent hidden work absent from the trace.

Every run trace must include:

- run identity;
- model profile identity;
- provider metadata where available;
- raw request reference;
- canonical request;
- task constitution;
- work graph;
- context pack references;
- node inputs;
- node outputs;
- validation results;
- scorecards;
- repair attempts;
- accepted artifacts;
- rejected artifacts where relevant;
- final answer;
- memory candidates;
- errors and retries.

Replay must reproduce controller decisions from saved inputs, saved outputs, and saved configuration. It does not need to guarantee bit-identical model generation across platforms.

## Evidence

- `README.md` requires an auditable trace and run manifests for replay and inspection.
- `docs/SPEC-1.md` requires every run to produce a structured reasoning trace.
- `ARCHITECTURE_STANDARDS.md` defines trace and replay standards.

## Invariants Involved

- The final answer must be synthesized from accepted artifacts.
- Every accepted artifact must be traceable to its inputs, node contract, validation result, and scorecard.
- Public machine-readable projections must declare schema versions once implementation begins.

## Alternatives Rejected

### Final free-form generation from raw prompt plus summaries

Rejected because it can invent unsupported work and weakens auditability.

### Hidden chain-of-thought as the product explanation

Rejected because Axia should expose artifact-level reasoning, not depend on raw hidden reasoning text as the source of truth.

### Best-effort logs instead of replayable manifests

Rejected because logs are usually incomplete, unstable, and difficult to use as controller evidence.

## Consequences

Axia becomes inspectable and debuggable. The tradeoff is that trace schemas must be maintained as public projections with compatibility discipline.

## Review Trigger

Review this decision if trace storage becomes too large or if a public projection needs to hide sensitive intermediate artifacts while preserving auditability.

