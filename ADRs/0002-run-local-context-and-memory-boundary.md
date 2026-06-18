# ADR-0002: Axia Owns Run-Local Context, Not Durable Memory

## Status

Accepted

## Context

Agentic reasoning requires context to be held, cached, refined, summarized, packed, scored, and replayed during a run. That is necessary process state. It is not the same as reliable AI memory.

Axia must be able to reason with context while remaining composable with a separate memory module.

## Decision

Axia owns run-local context management only.

Axia admits the following feature group:

- current task context;
- context packs;
- scoped evidence references;
- scratch summaries;
- intermediate artifacts;
- critique and repair records;
- scorecards;
- replay metadata;
- memory candidate projections.

Axia does not own:

- long-term user memory;
- durable preference memory;
- memory promotion;
- memory deletion;
- conflict resolution;
- forgetting policies;
- global memory search;
- memory reliability guarantees.

The boundary between Axia and durable memory is:

```text
Memory module -> supplies scoped context through ContextProvider
Axia -> assembles run-local context packs
Axia -> reasons over scoped context
Axia -> emits MemoryCandidate records
Memory module -> decides whether and how to persist them
```

`MemoryCandidate` is a projection, not a write command.

## Evidence

- `docs/SPEC-1.md` states that storage or retrieval exists only to support the reasoning process.
- `ARCHITECTURE_STANDARDS.md` defines the memory and context boundary.
- The project goal is modular LLM enhancement libraries with clear primary responsibilities.

## Invariants Involved

- Axia owns run-local context state only for the duration and replayability of a reasoning run.
- Axia must not own durable AI memory.
- Axia must remain valid when no memory module is installed.

## Alternatives Rejected

### Store reusable user memory directly in Axia

Rejected because it makes Axia responsible for durable memory correctness and lifecycle policy.

### Expose memory search as a core Axia feature

Rejected because global memory search belongs to a memory module. Axia may request scoped context, but it should not become the user-facing memory authority.

### Silently promote accepted artifacts into memory

Rejected because promotion requires policy, conflict checks, sensitivity handling, and user or module-level acceptance.

## Consequences

Axia can run without memory. When a memory module exists, Axia can use it through explicit context and candidate ports. This keeps the reasoning module independent but requires careful naming so run-local context is not accidentally described as durable memory.

## Review Trigger

Review this decision if the suite introduces a memory module contract that requires Axia to participate in stronger persistence semantics than candidate emission.

