# Axia Architecture Standards

## Purpose

This document defines the architecture standards for **Axia: Hierarchical Reasoning**.

Axia is a local-first reasoning orchestration module. Its primary responsibility is to improve small or local model output by decomposing work into bounded, typed, validated reasoning stages and synthesizing the final answer from accepted artifacts.

Axia is not a memory product, not a model-training system, and not a general agent platform. It may use run-local context state because agentic reasoning requires context to be held, packed, cached, refined, scored, and replayed during a run. That state does not make Axia the durable memory authority.

These standards adapt the Emergence Based Architecture flow to Axia's exact project shape:

```text
source
  -> observation
  -> invariant
  -> formation
  -> operation
  -> projection
  -> boundary
```

This is an admission order, not a claim that every runtime request must literally traverse every layer from top to bottom.

---

## Primary Responsibility

Axia owns reasoning orchestration.

That means Axia owns:

- canonical request formation;
- task constitution formation;
- bounded work graph formation;
- micro-agent contracts;
- run-local context packing;
- typed intermediate artifacts;
- schema and invariant validation;
- critique, repair, scoring, and retry decisions;
- final synthesis from accepted artifacts;
- replayable run traces;
- memory update candidates emitted from a run.

Axia does not own durable memory.

That means Axia does not own:

- long-term user memory;
- durable preference learning;
- autonomous memory promotion;
- cross-task identity memory;
- global memory search as a product feature;
- forgetting policies;
- conflict resolution for stored memories;
- memory reliability guarantees;
- training, fine-tuning, LoRA, reinforcement learning, or weight updates.

The durable memory authority belongs to a separate module. Axia may consume scoped context from that module and may emit memory candidates back to it.

---

## Reasoning Improvement Priority

Axia must prioritize systems that measurably improve small-model reasoning.

Reasoning improvement means the final answer is better because Axia:

- narrowed the model's job into explicit subtasks;
- made the task contract visible before planning;
- packed only scoped, relevant context;
- forced intermediate outputs into typed artifacts;
- validated artifacts before acceptance;
- scored artifacts against explicit rubrics;
- repaired or regenerated weak artifacts under limits;
- verified support before final synthesis;
- synthesized only from accepted artifacts;
- preserved enough trace to explain and replay the improvement.

The first implementation must include a baseline comparison against a single-shot model call. Advanced strategies such as self-consistency, branch search, verifier-guided selection, and multi-branch synthesis are candidates only after the simple typed graph has measurable evidence.

---

## Core Invariants

These invariants define Axia's architecture. They must be protected by code, tests, or governance checks once implementation begins.

### Reasoning Boundary

```text
Axia must remain a reasoning orchestration module.
```

Storage, retrieval, provider access, CLI, API, and UI are boundary mechanisms. They may support Axia, but they must not define Axia's internal truth.

### Run-Local Context

```text
Axia owns run-local context state only for the duration and replayability of a reasoning run.
```

Run-local context includes context packs, scratch summaries, intermediate artifacts, critique records, repair attempts, scorecards, and trace metadata.

Run-local context is not durable AI memory unless another module explicitly accepts it as memory.

### Durable Memory Boundary

```text
Axia must not own durable AI memory.
```

Axia may:

- request scoped context;
- cite received context in artifacts;
- summarize context for the current run;
- emit memory update candidates.

Axia must not:

- silently promote run artifacts into durable memory;
- decide global memory truth;
- perform autonomous long-term user profiling;
- expose durable memory search as its own core product surface;
- make memory reliability claims.

### Artifact Authority

```text
The final answer must be synthesized from accepted artifacts.
```

The final synthesis step may not invent hidden work that is absent from the run trace.

### Bounded Recursion

```text
Every critique, repair, refinement, or recursive reasoning loop must have explicit limits.
```

Limits include maximum calls, maximum retries per node, maximum depth, maximum wall-clock time, and stop conditions.

### Provider Boundary

```text
Axia must not let provider-specific behavior enter core reasoning structures.
```

Provider details belong behind the model-provider boundary. The core reasoning path receives normalized model responses, provider metadata, and errors translated into Axia-native error records.

Axia core owns the `ModelProvider` port, not any concrete provider stack. `crux-providers` may be used by an optional boundary adapter and by standalone composition roots, but Crux request objects, response objects, registries, lifecycle, and failures must be translated before entering core reasoning. A host application that already owns Crux must be able to inject a Crux-backed adapter rather than letting Axia create hidden duplicate provider ownership.

### Traceability

```text
Every accepted artifact must be traceable to its run inputs, node contract, validation result, and scorecard.
```

If an artifact is rejected, repaired, or superseded, the reason must remain inspectable.

### No Hidden Chain-of-Thought Product Dependence

```text
Axia should expose artifact-level reasoning, not rely on hidden free-form chain-of-thought as the product truth.
```

Visible traces should show contracts, inputs, outputs, validations, scorecards, repair decisions, and caveats. They should not depend on raw hidden reasoning text as the only explanation.

---

## Target Package Layout

The implementation should follow this shape unless a decision record admits a different structure.

```text
axia/
  pyproject.toml
  README.md
  ARCHITECTURE_STANDARDS.md
  docs/
    SPEC-1.md
    axia_spec.md
    DECISION_LEDGER.md
    INVARIANTS.md
    BOUNDARIES.md
    PROJECTIONS.md
  src/
    axia/
      source/
        request_record.py
        run_identity.py
        artifact_lineage.py
        context_reference.py
      observation/
        request_observation.py
        context_observation.py
        model_output_observation.py
        evidence_record.py
      invariant/
        run_limit_check.py
        schema_check.py
        context_scope_check.py
        artifact_support_check.py
        boundary_check.py
      formation/
        canonical_request.py
        task_constitution.py
        work_graph.py
        context_pack.py
        repair_plan.py
      operation/
        run_transition.py
        node_execution.py
        graph_execution.py
        critique_repair.py
        final_synthesis.py
      projection/
        run_manifest.py
        trace_view.py
        answer_view.py
        memory_candidate.py
      boundary/
        ports/
          model_provider.py
          context_provider.py
          memory_candidate_sink.py
          run_store.py
          clock.py
          id_provider.py
        adapters/
          crux_provider_adapter.py
          sqlite_run_store.py
          filesystem_artifact_store.py
        presentation/
          cli/
          api/
      policy/
        architecture_policy.py
        naming_policy.py
        dependency_policy.py
      shared/
        errors.py
        result.py
        ids.py
  tests/
    unit/
    contract/
    contradiction/
    integration/
    e2e/
```

This layout is not decorative. Each directory exists only if the implementation has the corresponding responsibility.

Do not create placeholder modules simply to satisfy the layout.

---

## Layer Standards

### `source/`

The source layer preserves what Axia receives.

Axia source records include:

- raw user request;
- normalized request identity;
- run identity;
- supplied context references;
- provider response identity;
- artifact lineage references.

Rules:

- Source records are canonical for the run.
- Source identity must be stable.
- Derived artifacts must preserve lineage to source records.
- No source material may be silently discarded.
- Source code must not perform model calls, storage IO, CLI handling, API handling, or durable memory decisions.

Good Axia names:

```text
request_record
run_identity
artifact_lineage
context_reference
provider_response_record
```

### `observation/`

The observation layer records what can be seen without admitting final structure.

Axia observations include:

- request features;
- explicit constraints;
- missing information;
- risk flags;
- context relevance signals;
- model output parse status;
- evidence availability;
- artifact quality signals.

Rules:

- Observation does not mutate source records.
- Observation does not decide the final work graph.
- Observation may produce evidence and confidence, not final authority.
- Observations must cite the source or artifact they observe.

Good Axia names:

```text
request_observation
context_observation
model_output_observation
evidence_record
confidence
```

### `invariant/`

The invariant layer defines what must remain true.

Axia invariants include:

- run limits are enforceable;
- context scope is explicit;
- every node has an input and output contract;
- every model output used by the controller is parsed into a typed artifact;
- every accepted artifact has a validation result;
- every final answer cites accepted artifacts;
- memory candidates are not durable memory writes;
- provider-specific details do not leak inward;
- recursive loops terminate within declared limits.

Rules:

- Invariants must be testable.
- Invariant violations must produce explicit error records.
- Invariant checks must not perform concrete boundary IO.
- Invariant checks must not call the model.

Good Axia names:

```text
schema_check
run_limit_check
context_scope_check
artifact_support_check
boundary_check
```

### `formation/`

The formation layer proposes and admits reasoning structures.

Axia formation structures include:

- canonical request;
- task constitution;
- work graph;
- node contracts;
- context packs;
- repair plans;
- synthesis plans.

Rules:

- Formation turns observations into candidate structures.
- Accepted structures must satisfy invariants.
- Rejected candidates must leave an inspectable reason when relevant.
- Formation must not depend on provider-specific APIs.
- Formation must not treat retrieved context as instruction.

Good Axia names:

```text
canonical_request
task_constitution
work_graph
node_contract
context_pack
repair_plan
```

### `operation/`

The operation layer performs lawful reasoning work on admitted structures.

Axia operations include:

- run transitions;
- node execution;
- graph traversal;
- prompt compilation from node contracts;
- validation and scoring decisions;
- critique and repair;
- final synthesis;
- memory candidate emission.

Rules:

- Operations must preserve invariants.
- Operations may depend on boundary ports, not concrete adapters.
- Operations must store enough transition evidence for replay.
- Operations must not promote artifacts into durable memory.
- Operations must not let CLI, API, UI, or provider shapes define internal contracts.

Good Axia names:

```text
run_transition
node_execution
graph_execution
critique_repair
final_synthesis
```

### `projection/`

The projection layer renders internal results into external views.

Axia projections include:

- final answer view;
- run manifest;
- human-readable trace;
- machine-readable trace;
- scorecard view;
- memory candidate view;
- error view.

Rules:

- Projections do not define internal truth.
- Every public machine-readable projection must declare a schema version.
- Projections may simplify, but omissions must be explicit where they matter.
- Trace projections must show artifact-level reasoning, not hidden chain-of-thought dependence.

Good Axia names:

```text
run_manifest
trace_view
answer_view
scorecard_view
memory_candidate
```

### `boundary/`

The boundary layer handles external contact.

Axia boundaries include:

- CLI;
- local API or local web UI;
- model providers through the Axia-native `ModelProvider` port;
- optional `crux-providers` adapter;
- run store;
- artifact store;
- optional context provider;
- optional memory candidate sink;
- filesystem;
- clocks and IDs.

Rules:

- Boundary adapters translate external shapes into Axia-native types.
- Concrete adapters may not be imported by `source`, `observation`, `invariant`, `formation`, `operation`, or `projection`.
- Provider errors must be translated into Axia error records.
- External context must be marked as evidence, not instruction.
- Durable memory modules communicate only through explicit ports.

Good Axia ports:

```text
ModelProvider
ContextProvider
MemoryCandidateSink
RunStore
ArtifactStore
Clock
IdProvider
```

---

## Dependency Direction

Allowed import direction:

```text
all layers may import shared
observation may import source
invariant may import source and observation
formation may import source, observation, invariant, and shared
operation may import source, observation, invariant, formation, shared, and boundary ports
projection may import source, formation, operation result types, and shared
boundary adapters may import boundary ports and Axia-native projection/input types
boundary presentation may import boundary adapters, projection, and operation entrypoints
policy checks may inspect all layers
```

Concrete boundary adapters must not be imported inward.

Boundary ports are protocol definitions. Operations may depend on them when an external capability is required. Adapters implement those ports at the edge.

### Current Enforced Import Checks

`make check-import-boundaries` protects the layers that exist today:

- `source` and `shared` must not import boundary mechanisms;
- `boundary.ports` must not import adapters or presentation;
- `boundary.adapters` must not import presentation.

This check is intentionally limited to admitted modules. It must be extended when `observation`, `invariant`, `formation`, `operation`, `projection`, or `policy` becomes necessary; Axia must not create empty layers merely to satisfy a generic architecture matrix.

Examples:

- `operation.node_execution` may depend on `boundary.ports.model_provider`.
- `operation.node_execution` must not depend on `boundary.adapters.crux_provider_adapter`.
- `formation.context_pack` may depend on Axia-native `ContextReference`.
- `formation.context_pack` must not depend on a memory database schema.

---

## Memory And Context Boundary

Axia's memory rule is strict:

```text
Axia manages context for reasoning runs.
Axia does not manage durable memory.
```

### Axia-Owned Run-Local State

Axia may own these during a run:

- current task context;
- context packs;
- retrieved evidence references;
- scratch summaries;
- intermediate outputs;
- critique and repair records;
- scorecards;
- run trace;
- replay metadata;
- memory candidates.

### External Memory-Owned State

A separate memory module owns:

- long-term storage;
- retrieval indexes;
- user preference records;
- project memory;
- memory promotion;
- memory deletion;
- conflict detection;
- forgetting policies;
- global memory search;
- memory reliability claims.

### Required Boundary Shape

The boundary between Axia and memory-capable modules should look like this:

```text
Memory module -> supplies scoped context through ContextProvider
Axia -> assembles run-local context packs
Axia -> reasons over scoped context
Axia -> emits MemoryCandidate records
Memory module -> decides whether and how to persist them
```

`MemoryCandidate` is a projection, not a write command.

A memory candidate must include:

- source run ID;
- source artifact IDs;
- candidate text or structured content;
- proposed scope;
- confidence or score;
- reason for proposal;
- caveats;
- sensitivity flags where known.

Axia must remain valid when no memory module is installed.

---

## Model Provider Boundary

Axia should use an Axia-native `ModelProvider` port as the model-access boundary. `crux-providers` is the expected optional adapter for the standalone local profile unless a later decision record supersedes that choice.

Rules:

- Axia must not implement provider-specific clients in the core.
- Axia core must not import `crux-providers`.
- Axia must not let provider model names define internal behavior.
- Provider request parameters belong in model profiles or adapter configuration.
- Provider metadata may be stored in run manifests.
- Provider errors must be translated at the boundary.
- Tests must include a deterministic fake provider that exercises parsing, retry, repair, scoring, and manifest capture.

Core reasoning code should see a normalized capability:

```text
model provider receives Axia-native request
model provider returns Axia-native response or Axia-native error
```

---

## Work Graph Standards

The standard reasoning path is:

```text
raw request
  -> canonical request
  -> task constitution
  -> work graph
  -> scoped context pack
  -> node execution
  -> validation
  -> scoring
  -> critique/repair when needed
  -> final synthesis
  -> trace projection
  -> memory candidate projection when useful
```

The work graph must be bounded.

Allowed node kinds include:

```text
canonicalize
constitute
decompose
assemble_context
analyze
draft
critique
repair
verify
synthesize
emit_memory_candidate
```

Node kinds should not be added because they sound agentic. A node kind is admitted only when it has a stable contract, validation rule, and reason to exist.

Every node contract must define:

- node kind;
- input schema;
- output schema;
- context scope;
- allowed tools or ports;
- retry limit;
- score policy;
- failure behavior.

---

## Trace And Replay Standards

Every run must produce a replayable trace.

The trace must include:

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

Replay does not need to guarantee bit-identical model output across platforms. Replay must be able to reproduce controller decisions from saved inputs, saved outputs, and saved configuration.

---

## Naming Standards

Names must carry real responsibility.

### Accepted Axia Terms

These terms are native to Axia:

```text
request
canonical_request
task_constitution
work_graph
node_contract
context_pack
artifact
evidence
scorecard
critique
repair
synthesis
trace
run_manifest
projection
boundary
port
adapter
memory_candidate
```

### Terms That Require Care

These terms may be used only with a narrow, documented responsibility:

```text
agent
controller
engine
orchestrator
service
manager
processor
pipeline
worker
repository
runtime
memory
```

Specific Axia allowances:

- `micro-agent` is allowed for a role prompt plus schema plus evaluator, not for an autonomous entity.
- `controller` is allowed for deterministic run control, not for MVC or generic web control.
- `engine` may appear in user-facing product framing only if it means reasoning orchestration, not a vague core module.
- `memory` may appear only for external memory boundaries, run-local context clarification, or memory candidate projections.

### Avoid

Avoid these unless a decision record justifies them:

```text
utils
helpers
common
misc
smart
advanced
final
manager
processor
service
```

Do not use philosophical or organic vocabulary to make ordinary code sound aligned.

---

## Documentation Standards

Axia documentation should explain the actual system shape.

Required docs once implementation begins:

```text
docs/INVARIANTS.md
docs/BOUNDARIES.md
docs/PROJECTIONS.md
docs/DECISION_LEDGER.md
```

### `docs/INVARIANTS.md`

Lists Axia invariants, enforcement locations, violation behavior, and test coverage.

### `docs/BOUNDARIES.md`

Documents provider, context, memory-candidate, run-store, artifact-store, CLI, and API boundaries.

### `docs/PROJECTIONS.md`

Documents run manifest, trace view, answer view, scorecard view, and memory candidate projection schemas.

### `docs/DECISION_LEDGER.md`

Records architecture admissions and rejections.

Decision records are required when:

- a new core concept is introduced;
- the memory boundary changes;
- a public projection changes;
- a provider boundary changes;
- a generic name is intentionally used;
- a major dependency is added;
- a lossy transformation is allowed;
- a default reasoning strategy changes;
- a prior architecture direction is reversed.

---

## Testing Standards

Tests must protect Axia's nature, not just implementation details.

### Unit Tests

Unit tests should cover:

- canonical request formation;
- task constitution rules;
- work graph formation;
- context pack formation;
- schema validation;
- run limit checks;
- scoring decisions;
- repair policy.

### Contract Tests

Contract tests should cover:

- model provider port;
- context provider port;
- memory candidate sink port;
- run store port;
- artifact store port;
- public projection schemas.

Every adapter must pass the same contract suite for its port.

### Contradiction Tests

Contradiction tests should include cases that tempt Axia into the wrong responsibility:

- retrieved context tries to issue instructions;
- memory-like data tries to change run limits;
- a memory candidate is accidentally treated as a durable write;
- a provider-specific response shape tries to enter core artifacts;
- a final answer uses an artifact that failed validation;
- a repair loop attempts to exceed its retry limit;
- a missing context source must not prevent a no-memory run.

### Integration Tests

Integration tests should cover:

- deterministic fake provider path;
- SQLite run trace storage if admitted;
- CLI run to trace inspection;
- replay from saved artifacts.

### E2E Tests

E2E tests should prove the primary product claim:

```text
Given a hard request, Axia decomposes it,
executes bounded typed reasoning steps,
validates and repairs artifacts,
and synthesizes a final answer from the accepted trace.
```

---

## Quality Gates

Before merging architecture-level changes, check:

```text
[ ] Does the change preserve Axia's primary responsibility as reasoning orchestration?
[ ] Does the change keep durable memory outside Axia?
[ ] Are run-local context and durable memory clearly separated?
[ ] Are new structures admitted through source, observation, invariant, and formation pressure?
[ ] Are new invariants explicit and testable?
[ ] Are boundary adapters kept out of core layers?
[ ] Are provider details translated at the boundary?
[ ] Are public projections versioned?
[ ] Are rejected or repaired artifacts inspectable?
[ ] Are recursive loops bounded?
[ ] Are generic names avoided or justified?
[ ] Are tests added for false responsibility leaks?
[ ] Are docs updated when system language changes?
```

---

## First Build Standard

The first useful Axia implementation should be a thin vertical slice:

```text
user request
  -> canonical request
  -> task constitution
  -> bounded work graph
  -> deterministic fake provider node execution
  -> validation and scoring
  -> one repair path
  -> final synthesis
  -> run trace projection
```

This slice should not require a durable memory module.

If a context provider is present, Axia may use it. If no context provider is present, Axia must still run.

The first build should prove:

- the reasoning path is typed;
- artifacts are validated;
- repair is bounded;
- trace replay is possible;
- provider access is behind a boundary;
- durable memory is not part of Axia's responsibility.

---

## Summary

Axia succeeds when it reads as a reasoning system, not as a generic agent framework and not as a memory product.

Its job is to make weak model calls useful by narrowing each call, preserving artifacts, enforcing contracts, repairing failures, and synthesizing from a trace.

Memory-capable systems can improve Axia, and Axia can improve memory-capable systems by producing high-quality trace-derived candidates. But durable memory remains a separate responsibility behind an explicit boundary.
