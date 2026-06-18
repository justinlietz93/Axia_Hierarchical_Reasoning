# Axia Architecture Decision Records

This folder contains architecture decision records for Axia.

Each ADR admits a feature or feature group into the project architecture. ADRs should stay specific: they must identify the capability, the boundary it belongs to, the invariant it protects, and the conditions that would cause the decision to be reviewed.

## Index

| ADR | Decision |
|---|---|
| [ADR-0001](0001-reasoning-orchestration-boundary.md) | Axia owns reasoning orchestration |
| [ADR-0002](0002-run-local-context-and-memory-boundary.md) | Axia owns run-local context, not durable memory |
| [ADR-0003](0003-canonical-request-and-task-constitution.md) | Axia forms canonical requests and task constitutions before planning |
| [ADR-0004](0004-bounded-work-graph-and-micro-agent-contracts.md) | Axia executes bounded work graphs through micro-agent contracts |
| [ADR-0005](0005-validation-scoring-and-repair.md) | Axia validates, scores, and repairs artifacts before acceptance |
| [ADR-0006](0006-artifact-trace-replay-and-final-synthesis.md) | Axia synthesizes final answers from accepted artifacts and replayable traces |
| [ADR-0007](0007-model-provider-boundary-and-fake-provider.md) | Axia keeps model access behind a provider boundary and tests with a deterministic fake provider |
| [ADR-0008](0008-local-first-cli-and-run-store.md) | Axia starts as a local-first CLI with a run store and later local UI boundary |
| [ADR-0009](0009-reasoning-improvement-systems-and-benchmarks.md) | Axia prioritizes measurable reasoning-improvement systems |
