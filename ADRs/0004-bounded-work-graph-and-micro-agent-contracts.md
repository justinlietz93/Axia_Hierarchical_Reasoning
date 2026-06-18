# ADR-0004: Bounded Work Graphs And Micro-Agent Contracts

## Status

Accepted

## Context

Axia improves small-model output by narrowing each model call. The project should not rely on one broad prompt or unbounded autonomous loops. It needs explicit steps, explicit contracts, and explicit termination conditions.

## Decision

Axia admits bounded work graph execution through micro-agent contracts.

A work graph is a typed graph of reasoning nodes derived from the task constitution. Cycles are allowed only through explicit refinement nodes with retry limits.

Allowed node kinds include:

- canonicalize;
- constitute;
- decompose;
- assemble_context;
- analyze;
- draft;
- critique;
- repair;
- verify;
- synthesize;
- emit_memory_candidate.

A micro-agent is not an autonomous entity. It is a role prompt plus schema plus evaluator under deterministic controller policy.

Every node contract must define:

- node kind;
- input schema;
- output schema;
- context scope;
- allowed tools or ports;
- retry limit;
- score policy;
- failure behavior.

## Evidence

- `README.md` describes breaking requests into smaller validated steps.
- `docs/SPEC-1.md` requires bounded reasoning loops and prevents unbounded recursive agent calls.
- `ARCHITECTURE_STANDARDS.md` defines work graph standards and allows `micro-agent` only as a narrow contract term.

## Invariants Involved

- Every node must have an input and output contract.
- Every recursive or refinement loop must have explicit limits.
- Agents must not share implicit global memory.
- Work graph execution must remain replayable from saved artifacts and decisions.

## Alternatives Rejected

### Single-shot answer generation

Rejected because it asks the small model to carry too many responsibilities at once.

### Free-form autonomous agent loops

Rejected because they are hard to bound, replay, validate, and compose.

### Multiple autonomous agents with shared hidden state

Rejected because it violates the context boundary and makes causality in the trace unclear.

## Consequences

Axia gets inspectable reasoning steps and stronger failure isolation. The cost is controller complexity and additional model calls. That cost must be controlled through modes, budgets, and benchmark evidence.

## Review Trigger

Review this decision if a feature requires graph behavior that cannot be represented as typed bounded nodes.

