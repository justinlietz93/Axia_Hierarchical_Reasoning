# ADR-0003: Canonical Request And Task Constitution Before Planning

## Status

Accepted

## Context

Small local models fail when asked to infer intent, plan, remember constraints, reason, critique, and format in one pass. Axia's first responsibility is to reduce that burden by turning the user's request into explicit structures before any work graph is formed.

## Decision

Axia admits canonical request formation and task constitution formation as first-class reasoning features.

The canonical request records:

- user intent;
- deliverable type;
- explicit constraints;
- unknowns;
- risk flags;
- requested output format;
- expected depth;
- context or tool needs.

The task constitution records:

- mission;
- deliverable definition;
- constraints;
- non-goals;
- allowed operations;
- required evidence;
- quality rubric;
- stop criteria;
- maximum recursion depth;
- maximum model calls;
- maximum wall-clock time.

The work graph may not be generated until the task constitution exists.

## Evidence

- `README.md` lists canonicalization and task contract definition before work graph construction.
- `docs/SPEC-1.md` requires canonical request and task constitution as MVP decomposition stages.
- `docs/axia_spec.md` defines task constitution as an immutable run-level contract.

## Invariants Involved

- Every run must declare the task it is trying to satisfy.
- Every work graph must be derived from an explicit task constitution.
- Stop criteria and run limits must exist before recursive or repair behavior begins.

## Alternatives Rejected

### Generate a plan directly from the raw request

Rejected because raw requests are often ambiguous, conversational, or underspecified. Planning directly from them hides assumptions.

### Let each node reinterpret the user's intent

Rejected because it produces drift and makes replay harder to audit.

### Treat the task constitution as mutable background state

Rejected because a moving contract breaks traceability. User-initiated changes should create explicit revision records.

## Consequences

Axia gains a stable run contract and can explain why a work graph exists. The tradeoff is an extra upfront stage, but it protects downstream reasoning from hidden assumptions.

## Review Trigger

Review this decision if benchmark evidence shows that a lighter request contract produces equal or better reliability without losing traceability.

