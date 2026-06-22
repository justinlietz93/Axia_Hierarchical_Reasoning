# Axia TODO

This TODO translates the accepted ADRs into a practical implementation sequence.

The hierarchy is:

```text
Phase -> Task -> Step
```

Each task cites the ADRs that justify it. Do not treat this as a generic app backlog. The sequence exists to prove Axia's primary claim: small/local model output improves when reasoning is decomposed, typed, validated, repaired, measured, and synthesized from an auditable trace.

---

## Phase 0 - Architecture Baseline

### Task 0.1 - Lock Axia's Responsibility Boundary

ADRs: `ADR-0001`, `ADR-0002`, `ADR-0009`

- [x] Step 0.1.1 - Treat Axia as a reasoning orchestration module, not a general agent platform.
- [x] Step 0.1.2 - Keep durable memory, memory search, promotion, forgetting, and profile learning outside Axia.
- [x] Step 0.1.3 - Keep model training, fine-tuning, LoRA, RLHF, and weight updates outside Axia.
- [x] Step 0.1.4 - Define all external capabilities as boundary ports before admitting adapters.
- [x] Step 0.1.5 - Add an architecture check or review checklist item for memory-boundary leaks.

### Task 0.2 - Establish Project Skeleton

ADRs: `ADR-0001`, `ADR-0008`

- [x] Step 0.2.1 - Create Python package layout under `src/axia/`.
- [x] Step 0.2.2 - Add `pyproject.toml` with Python version, package metadata, and initial test dependencies.
- [ ] Step 0.2.3 - Add top-level packages for source, observation, invariant, formation, operation, projection, boundary, policy, and shared only as they become necessary.
- [x] Step 0.2.4 - Add a minimal test runner command.
- [x] Step 0.2.5 - Add import-boundary notes or a future import-linter task matching `ARCHITECTURE_STANDARDS.md`.

### Task 0.3 - Define Native Types Before Mechanisms

ADRs: `ADR-0001`, `ADR-0003`, `ADR-0004`, `ADR-0006`

- [x] Step 0.3.1 - Define `RunId`, `ArtifactId`, `NodeId`, and stable hash primitives.
- [x] Step 0.3.2 - Define base error/result types.
- [x] Step 0.3.3 - Define source records for raw request, run identity, provider response identity, and artifact lineage.
- [x] Step 0.3.4 - Add tests for stable IDs and deterministic hashing.

---

## Phase 1 - Local-First Execution Boundary

### Task 1.1 - Implement Provider Port

ADRs: `ADR-0007`, `ADR-0001`

- [x] Step 1.1.1 - Define an Axia-native `ModelProvider` port.
- [x] Step 1.1.2 - Define normalized request, response, metadata, and provider error records.
- [x] Step 1.1.3 - Ensure core reasoning code depends only on the port, not concrete provider adapters.
- [x] Step 1.1.4 - Add contract tests for provider success, malformed output, timeout-like failure, and metadata capture.

### Task 1.2 - Implement Deterministic Fake Provider

ADRs: `ADR-0007`, `ADR-0009`

- [x] Step 1.2.1 - Build a schema-aware fake provider for offline tests.
- [x] Step 1.2.2 - Support fixed valid JSON responses keyed by prompt markers.
- [x] Step 1.2.3 - Support configured malformed JSON, empty response, timeout-like failure, and schema-mismatch cases.
- [x] Step 1.2.4 - Emit deterministic fake provider metadata.
- [x] Step 1.2.5 - Prove retry, repair, scoring, and manifest capture can run without a live model.

### Task 1.3 - Add Crux Provider Adapter

ADRs: `ADR-0007`

- [x] Step 1.3.1 - Add a boundary adapter around `crux-providers` without importing Crux from core reasoning modules.
- [x] Step 1.3.2 - Translate Axia-native model requests into `crux-providers` requests.
- [x] Step 1.3.3 - Allow host applications to inject an already configured Crux-backed adapter or provider dependency.
- [x] Step 1.3.4 - Translate provider responses and provider errors back into Axia-native records.
- [x] Step 1.3.5 - Add a startup/import smoke test for the expected optional `crux-providers` public surface.

### Task 1.4 - Create Local CLI Skeleton

ADRs: `ADR-0008`

- [ ] Step 1.4.1 - Add executable `axia ask`.
- [ ] Step 1.4.2 - Add executable `axia run`.
- [x] Step 1.4.3 - Add `axia trace`.
- [x] Step 1.4.4 - Add `axia replay`.
- [ ] Step 1.4.5 - Add real `axia profiles list`.
- [ ] Step 1.4.6 - Add executable `axia benchmark run --suite baseline`.
- [x] Step 1.4.7 - Do not add `axia memory search`; that belongs to a memory module.

### Task 1.5 - Implement Local Run Store

ADRs: `ADR-0008`, `ADR-0006`

- [x] Step 1.5.1 - Define a `RunStore` port.
- [x] Step 1.5.2 - Add a SQLite run-store adapter.
- [x] Step 1.5.3 - Store run manifests, nodes, artifacts, scorecards, errors, context logs, and memory candidates.
- [x] Step 1.5.4 - Add contract tests proving the run store is trace/replay storage, not durable memory.

### Task 1.6 - Implement The Executable Local Reasoning Path

ADRs: `ADR-0001`, `ADR-0006`, `ADR-0007`, `ADR-0008`

- [ ] Step 1.6.1 - Add a standalone local model-profile loader and a composition root that binds an Axia-native provider to the selected profile.
- [ ] Step 1.6.2 - Implement a bounded run controller that forms the canonical request, constitution, graph, artifacts, scorecards, final answer, and replayable manifest.
- [ ] Step 1.6.3 - Replace `axia ask` and `axia run` stubs with real local execution.
- [ ] Step 1.6.4 - Persist each executable run before exposing it to trace, replay, or the local web UI.
- [ ] Step 1.6.5 - Run an end-to-end smoke test against an installed tiny Ollama model before claiming the local core path is complete.

---

## Phase 2 - Request Formation

### Task 2.1 - Implement Canonical Request Formation

ADRs: `ADR-0003`, `ADR-0009`

- [x] Step 2.1.1 - Define the canonical request schema.
- [x] Step 2.1.2 - Capture user intent, deliverable type, constraints, unknowns, risk flags, output format, expected depth, and context needs.
- [x] Step 2.1.3 - Generate canonical requests through a schema-constrained micro-agent or fake-provider equivalent.
- [x] Step 2.1.4 - Add deterministic validation for required fields and invalid combinations.
- [x] Step 2.1.5 - Add contradiction tests for ambiguous or underspecified requests.

### Task 2.2 - Implement Task Constitution Formation

ADRs: `ADR-0003`, `ADR-0004`

- [x] Step 2.2.1 - Define the task constitution schema.
- [x] Step 2.2.2 - Include mission, deliverable definition, constraints, non-goals, allowed operations, required evidence, rubric, stop criteria, max depth, max calls, retries, and max time.
- [x] Step 2.2.3 - Treat the constitution as immutable for a run unless a user revision creates a new explicit revision.
- [x] Step 2.2.4 - Add tests proving the work graph cannot be generated without a constitution.
- [x] Step 2.2.5 - Add tests for run-limit presence before critique/repair loops can start.

---

## Phase 3 - Bounded Work Graph

### Task 3.1 - Define Work Graph Model

ADRs: `ADR-0004`, `ADR-0003`

- [x] Step 3.1.1 - Define node, edge, dependency, and graph schemas.
- [x] Step 3.1.2 - Support standard node kinds: canonicalize, constitute, retrieve, analyze, draft, critique, repair, merge, verify, finalize, and emit_memory_candidate.
- [x] Step 3.1.3 - Require every node to declare input schema, output schema, context scope, retry policy, score policy, and failure behavior.
- [x] Step 3.1.4 - Reject unbounded cycles.
- [x] Step 3.1.5 - Add tests for topological order and bounded refinement cycles.

### Task 3.2 - Build Standard Reasoning Graph

ADRs: `ADR-0004`, `ADR-0009`

- [x] Step 3.2.1 - Build standard graph: canonicalize -> constitution -> retrieve -> plan -> draft -> critique -> repair -> verify -> final -> memory_candidates.
- [x] Step 3.2.2 - Keep each node narrow enough for a small local model.
- [x] Step 3.2.3 - Make graph construction deterministic from the constitution.
- [x] Step 3.2.4 - Add a fixture proving the same constitution produces the same graph.

### Task 3.3 - Implement Micro-Agent Contracts

ADRs: `ADR-0004`, `ADR-0007`

- [x] Step 3.3.1 - Define micro-agent as role prompt plus schema plus evaluator.
- [x] Step 3.3.2 - Implement prompt compilation from node contract and context pack.
- [x] Step 3.3.3 - Ensure micro-agents do not share implicit global memory.
- [x] Step 3.3.4 - Add tests proving provider output must pass through typed parsing before the controller can use it.

---

## Phase 4 - Context Boundary

### Task 4.1 - Implement Run-Local Context Packing

ADRs: `ADR-0002`, `ADR-0004`, `ADR-0009`

- [x] Step 4.1.1 - Define `ContextPack` and `ContextReference` schemas.
- [x] Step 4.1.2 - Pack node instruction, constitution subset, required prior artifacts, scoped context records, and output schema.
- [x] Step 4.1.3 - Exclude unrelated nodes, full logs, redundant context, unnecessary rejected artifacts, and hidden chain-of-thought.
- [x] Step 4.1.4 - Enforce per-node context budgets.
- [x] Step 4.1.5 - Add tests for stable context ordering.

### Task 4.2 - Implement Context Provider Port

ADRs: `ADR-0002`

- [x] Step 4.2.1 - Define `ContextProvider` as a boundary port.
- [x] Step 4.2.2 - Make Axia valid when no context provider is installed.
- [x] Step 4.2.3 - Treat returned context as evidence, not instruction.
- [x] Step 4.2.4 - Log context queries and result references in the run trace.
- [x] Step 4.2.5 - Add contradiction tests where retrieved context attempts to change tool permissions, run limits, or memory policy.

### Task 4.3 - Emit Memory Candidates

ADRs: `ADR-0002`, `ADR-0006`

- [x] Step 4.3.1 - Define `MemoryCandidate` projection schema.
- [x] Step 4.3.2 - Include source run ID, source artifact IDs, content, proposed scope, confidence, reason, caveats, and tags.
- [x] Step 4.3.3 - Emit candidates only as projections.
- [x] Step 4.3.4 - Do not persist candidates into durable memory inside Axia.
- [x] Step 4.3.5 - Add tests proving memory candidates are not durable writes.

---

## Phase 5 - Validation, Scoring, And Repair

### Task 5.1 - Implement Structured Parsing And Schema Validation

ADRs: `ADR-0005`, `ADR-0007`

- [x] Step 5.1.1 - Parse every model output used by the controller.
- [x] Step 5.1.2 - Reject malformed JSON.
- [x] Step 5.1.3 - Reject schema-mismatched JSON.
- [x] Step 5.1.4 - Preserve validation errors in node results.
- [x] Step 5.1.5 - Add tests for parse failure, missing fields, wrong type, and valid output.

### Task 5.2 - Implement Scorecards

ADRs: `ADR-0005`, `ADR-0009`

- [x] Step 5.2.1 - Define scorecard schema.
- [x] Step 5.2.2 - Score relevance, completeness, consistency, specificity, evidence use, constraint compliance, and final usability.
- [x] Step 5.2.3 - Prefer deterministic checks where possible.
- [x] Step 5.2.4 - Bound model-based critique behind schemas and thresholds.
- [x] Step 5.2.5 - Store scorecards with artifact and node lineage.

### Task 5.3 - Implement Bounded Repair

ADRs: `ADR-0005`, `ADR-0004`

- [x] Step 5.3.1 - Define repair policy thresholds.
- [x] Step 5.3.2 - Repair only specific failed dimensions.
- [x] Step 5.3.3 - Include failed artifact, scorecard, relevant evidence, and target threshold in repair context.
- [x] Step 5.3.4 - Enforce retry limits per node and total run limits.
- [x] Step 5.3.5 - Add contradiction tests for repair loops attempting to exceed limits.

---

## Phase 6 - Trace, Replay, And Final Synthesis

### Task 6.1 - Implement Run Manifest Projection

ADRs: `ADR-0006`, `ADR-0008`

- [x] Step 6.1.1 - Define run manifest schema.
- [x] Step 6.1.2 - Include model profile identity, prompt hashes, canonical request, constitution, work graph, node results, final answer, memory candidates, and metrics.
- [x] Step 6.1.3 - Version public manifest schema.
- [x] Step 6.1.4 - Add tests for complete trace requirements.

### Task 6.2 - Implement Final Synthesis

ADRs: `ADR-0006`, `ADR-0005`

- [x] Step 6.2.1 - Synthesize final answers from accepted artifacts only.
- [x] Step 6.2.2 - Include constitution, accepted outputs, scorecards, unresolved caveats, requested format, and style constraints.
- [x] Step 6.2.3 - Reject or repair final answers that introduce unsupported major claims.
- [x] Step 6.2.4 - Add tests where final synthesis tries to use a rejected artifact.

### Task 6.3 - Implement Replay

ADRs: `ADR-0006`

- [x] Step 6.3.1 - Replay graph traversal from saved manifest and saved node outputs.
- [x] Step 6.3.2 - Reproduce validation decisions and score comparisons from saved artifacts.
- [x] Step 6.3.3 - Reproduce final selected artifact.
- [x] Step 6.3.4 - Add CLI support for `axia replay RUN_ID`.
- [x] Step 6.3.5 - Add tests proving prompt hashes and graph order remain stable.

### Task 6.4 - Implement Trace Display

ADRs: `ADR-0006`, `ADR-0008`

- [x] Step 6.4.1 - Add CLI support for `axia trace RUN_ID`.
- [x] Step 6.4.2 - Display request interpretation, task contract, scoped context records, draft score, repair summary, verification result, and final acceptance.
- [x] Step 6.4.3 - Do not expose hidden chain-of-thought as the product truth.
- [x] Step 6.4.4 - Include machine-readable trace output for tests and tooling.

---

## Phase 7 - Reasoning Improvement Measurement

### Task 7.1 - Build Baseline Benchmark Harness

ADRs: `ADR-0009`

- [x] Step 7.1.1 - Create a fixed benchmark suite of at least 20 tasks.
- [x] Step 7.1.2 - Add single-shot tiny model runner.
- [x] Step 7.1.3 - Add Axia quick-mode runner.
- [x] Step 7.1.4 - Add Axia standard-mode runner.
- [x] Step 7.1.5 - Store benchmark inputs, outputs, scorecards, run IDs, and summary metrics.

### Task 7.2 - Score Reasoning Improvement

ADRs: `ADR-0009`, `ADR-0005`

- [x] Step 7.2.1 - Score final answer usefulness.
- [x] Step 7.2.2 - Score task decomposition quality.
- [x] Step 7.2.3 - Score schema validity.
- [x] Step 7.2.4 - Score constraint compliance.
- [x] Step 7.2.5 - Score evidence use and support.
- [x] Step 7.2.6 - Score repair effectiveness.
- [x] Step 7.2.7 - Score replayability.

### Task 7.3 - Define MVP Improvement Gate

ADRs: `ADR-0009`

- [x] Step 7.3.1 - Compare Axia standard mode against single-shot baseline.
- [x] Step 7.3.2 - Require median score improvement before claiming MVP reasoning uplift.
- [x] Step 7.3.3 - Record failure categories when Axia does not improve output.
- [x] Step 7.3.4 - Use benchmark results to tune graph, prompts, scoring thresholds, and repair policy.

---

## Phase 8 - Extension Boundaries

### Task 8.1 - Admit Advanced Reasoning Strategies Only With Evidence

ADRs: `ADR-0009`, `ADR-0004`

- [x] Step 8.1.1 - Treat self-consistency as a candidate strategy, not a default.
- [x] Step 8.1.2 - Treat verifier-guided selection as a candidate strategy, not a default.
- [x] Step 8.1.3 - Treat branch search and multi-branch synthesis as candidate strategies, not defaults.
- [x] Step 8.1.4 - Require bounded call budgets and inspectable artifacts for each candidate.
- [x] Step 8.1.5 - Compare each candidate against standard graph before admission.

### Task 8.2 - Add Local Web UI After CLI Trace Stabilizes

ADRs: `ADR-0008`, `ADR-0006`

- [x] Step 8.2.1 - Build local UI only after run manifest and trace views are stable.
- [x] Step 8.2.2 - Show run state, completed nodes, scorecards, accepted artifacts, final answer, and memory candidates.
- [x] Step 8.2.3 - Keep UI as projection and boundary presentation only.
- [x] Step 8.2.4 - Do not let UI shape define internal reasoning contracts.

### Task 8.3 - Integrate External Memory Module Through Ports

ADRs: `ADR-0002`, `ADR-0001`

- [x] Step 8.3.1 - Connect an external memory module through `ContextProvider`.
- [x] Step 8.3.2 - Send memory candidates through `MemoryCandidateSink` only when configured.
- [x] Step 8.3.3 - Keep persistence, promotion, forgetting, conflict resolution, and search outside Axia.
- [x] Step 8.3.4 - Add integration tests proving Axia still runs without the memory module.

### Task 8.4 - Integrate External Data-Curation Or Export Module

ADRs: `ADR-0001`, `ADR-0006`, `ADR-0009`

- [x] Step 8.4.1 - Emit reasoning example candidates from accepted traces.
- [x] Step 8.4.2 - Emit training slice candidates from useful interaction segments.
- [x] Step 8.4.3 - Keep export, dataset governance, and training outside Axia.
- [x] Step 8.4.4 - Require explicit user approval before any external export.

---

## Phase 9 - Completion Integrity

### Task 9.1 - Resolve Or Isolate SGDA Scaffold Placeholders

Source: `docs/scaffold_sgda_docs.py`

- [ ] Step 9.1.1 - Decide whether the SGDA documentation scaffold is an active Axia tool or an archived external reference.
- [ ] Step 9.1.2 - If retained, replace its emitted `TODO` and placeholder material with Axia-specific, verified documentation behavior.
- [ ] Step 9.1.3 - If not retained, move it outside the active documentation surface and remove it from Axia completion claims.

### Task 9.2 - Reconcile Public Status With Executable Reality

Source: `README.md`, `src/axia/boundary/presentation/cli.py`

- [ ] Step 9.2.1 - Update the README status once the executable local reasoning path exists; until then, distinguish tested components from runnable product behavior.
- [ ] Step 9.2.2 - Remove every `not_implemented` response from user-facing CLI commands only when its real execution path and end-to-end test exist.

---

## ADR Coverage Checklist

- [x] `ADR-0001` - Reasoning orchestration boundary is enforced.
- [x] `ADR-0002` - Run-local context and durable memory are separated.
- [x] `ADR-0003` - Canonical request and task constitution are implemented before planning.
- [x] `ADR-0004` - Work graph and micro-agent contracts are bounded and typed.
- [x] `ADR-0005` - Validation, scoring, and bounded repair gate artifact acceptance.
- [x] `ADR-0006` - Final synthesis, trace, and replay are artifact-grounded.
- [x] `ADR-0007` - Provider boundary and deterministic fake provider are tested.
- [x] `ADR-0008` - Local-first CLI and run store prove the core path.
- [x] `ADR-0009` - Reasoning improvement is benchmarked against single-shot baseline.
