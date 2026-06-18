# ADR-0008: Local-First CLI And Run Store

## Status

Accepted

## Context

Axia is in planning and specification stage. The first implementation should be small and inspectable: one CLI path, one local model profile, one deterministic fake provider, one run store, and one standard reasoning graph.

The system should remain local-first by default and should not require network services, cloud storage, or a web server to prove the core reasoning path.

## Decision

Axia admits a local-first CLI and run store as MVP boundary features.

The first build should provide:

- `axia ask`;
- `axia run`;
- `axia trace`;
- `axia replay`;
- profile inspection;
- local run manifest storage;
- local artifact storage where needed.

A local web UI may be admitted later as a projection and boundary layer over the same run store and trace views. It must not define internal reasoning truth.

The run store records reasoning traces and artifacts. It is not a durable memory store.

## Evidence

- `README.md` says the project is CLI first with a minimal local web UI later.
- `README.md` lists planned MVP commands for ask, run, trace, replay, profiles, and benchmark execution.
- `ARCHITECTURE_STANDARDS.md` narrows the current command surface so memory search does not become an Axia-owned durable memory feature.


## Invariants Involved

- Axia must be local-first by default.
- Run artifacts must support trace and replay.
- Boundary presentation must not define internal truth.
- The run store must not become durable memory ownership.

## Alternatives Rejected

### Start with a web server as the center

Rejected because it puts presentation before the reasoning path and makes the first proof larger than needed.

### Require cloud services

Rejected because local-first operation is a project property.

### Treat the run store as long-term memory

Rejected because run storage supports trace and replay. Durable memory belongs to a separate module.

## Consequences

Axia can prove the core reasoning path with a small local surface. The CLI and run store also provide stable test targets. The tradeoff is that richer interactive inspection waits until the trace model is stable.

## Review Trigger

Review this decision when the CLI trace and replay path is stable enough to justify a local web UI or when a separate memory module defines a command surface Axia should integrate with.
