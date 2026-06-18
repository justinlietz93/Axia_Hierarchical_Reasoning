# ADR-0001: Axia Owns Reasoning Orchestration

## Status

Accepted

## Context

Axia is being built as one module in a suite of loosely coupled LLM enhancement libraries. Each library needs a primary responsibility so it can be plugged in or removed without forcing other modules to inherit unrelated concerns.

The project materials define Axia as a local-first hierarchical reasoning tool that improves small-model output through decomposition, validation, critique, repair, synthesis, and traceability. The clarified project boundary is that Axia is not a memory product, training system, or general agent platform.

## Decision

Axia's primary responsibility is reasoning orchestration.

Axia admits the following feature group:

- canonical request formation;
- task constitution formation;
- bounded work graph formation;
- typed micro-agent execution;
- validation, scoring, critique, repair, and retry decisions;
- final synthesis from accepted artifacts;
- trace and replay projection;
- memory candidate emission as an output boundary.

Axia does not admit durable memory ownership, model training, autonomous agent autonomy, or general-purpose tool execution as core responsibilities.

## Evidence

- `README.md` frames Axia as a local-first utility for improving small-model output through deterministic hierarchical reasoning.
- `docs/SPEC-1.md` frames Axia as a reasoning orchestration tool, not a memory product.
- `ARCHITECTURE_STANDARDS.md` defines Axia as a reasoning orchestration module with run-local context only.

## Invariants Involved

- Axia must remain a reasoning orchestration module.
- Storage, retrieval, provider access, CLI, API, and UI are boundary mechanisms.
- Final answers must be synthesized from accepted artifacts.

## Alternatives Rejected

### Make Axia a general agent platform

Rejected because it would blur the primary responsibility and make Axia harder to compose with other libraries.

### Make Axia a memory product

Rejected because durable memory requires separate authority over storage, retrieval, promotion, forgetting, conflict resolution, and reliability guarantees.

### Make Axia a model-training system

Rejected because training, fine-tuning, LoRA, reinforcement learning, and weight updates are explicitly outside the product claim.

## Consequences

Axia can be composed with memory, retrieval, provider, UI, and training-data modules without owning them. The cost is that Axia must maintain explicit boundary ports for external capabilities instead of assuming those capabilities are internal.

## Review Trigger

Review this decision if Axia is asked to own durable memory, autonomous tool execution, model training, or cross-task user identity as a core product responsibility.

