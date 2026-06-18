# ADR-0005: Validation, Scoring, And Bounded Repair

## Status

Accepted

## Context

Small models often produce malformed JSON, incomplete artifacts, unsupported claims, or fluent but weak reasoning. Axia's product claim depends on not accepting model output just because it was generated.

## Decision

Axia admits validation, scoring, critique, and bounded repair as core reasoning features.

Every model output used by the controller must pass through validation before acceptance.

Validation tiers are:

1. Parse validity.
2. Schema validity.
3. Domain invariant validity.
4. Rubric score.
5. Unsupported-claim and banned-action checks where relevant.

Artifacts that fail validation may be repaired or retried only within declared limits. Rejected artifacts and repair reasons must remain inspectable when they affect the run.

## Evidence

- `README.md` requires validated steps, scoring, and repair of weak outputs.
- `docs/SPEC-1.md` requires final output to be generated from validated intermediate artifacts.
- `ARCHITECTURE_STANDARDS.md` defines artifact authority, bounded recursion, and traceability invariants.

## Invariants Involved

- Every accepted artifact must have a validation result.
- Every accepted artifact must have a scorecard when scoring is part of the node contract.
- Repair loops must terminate within declared limits.
- The final answer must be synthesized from accepted artifacts.

## Alternatives Rejected

### Trust model output after prompting for JSON

Rejected because prompt-only formatting is not reliable enough for controller decisions.

### Use unbounded self-repair

Rejected because weak models can loop, reinforce errors, or consume the entire budget.

### Hide failed artifacts

Rejected because failures are evidence. They are needed for debugging, replay, and future improvement.

## Consequences

Axia can reject false structure and explain repair decisions. The tradeoff is extra implementation work for schemas, scorecards, and error records.

## Review Trigger

Review this decision when real benchmark data shows which validation tiers are too strict, too weak, or too expensive for specific task families.

