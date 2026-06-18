
![alt text](https://raw.githubusercontent.com/justinlietz93/Axia_Hierarchical_Reasoning/main/assets/axia_banner.png)

# Hierarchical Reasoning Engine for LLMs

Axia is a planned local-first LLM utility for improving small-model output through deterministic hierarchical reasoning. It treats the model as one narrow semantic operator inside a controlled reasoning-improvement system, not as the whole system.

The goal is simple: break a hard request into smaller validated steps, preserve the intermediate artifacts, score the work, repair weak outputs, and synthesize a better final answer from an auditable trace.

## Status

Planning and specification stage.

This repository currently contains the starting architecture and source material for the project. The implementation is not complete yet.

## Core idea

Small models often fail because they are asked to plan, remember, reason, critique, format, and answer in one pass. Axia separates those jobs into bounded steps:

```text
request
  -> canonicalize
  -> define task contract
  -> build work graph
  -> execute narrow reasoning steps
  -> validate outputs
  -> critique and repair
  -> synthesize final answer
  -> store trace and emit memory candidates
```

Axia owns the reasoning process. It may assemble, cache, summarize, and pass context during a run because reasoning needs working state. Durable AI memory is a separate module responsibility. Axia can consume scoped context from that module and emit trace-derived memory candidates back to it, but it does not own memory search, promotion, forgetting, or long-term user profiles.

## Reasoning improvement priorities

Axia should prioritize systems that measurably improve reasoning quality:

- explicit task decomposition before answer generation
- task constitutions with constraints, non-goals, rubrics, and stop conditions
- typed work graphs with narrow node contracts
- schema-constrained intermediate artifacts
- deterministic validation before acceptance
- scorecards and verifier-style checks
- bounded critique, repair, and regeneration loops
- selective context packing with provenance
- final synthesis from accepted artifacts only
- replayable traces and benchmarks against single-shot baselines

## Intended properties

- Local-first by default
- Provider-agnostic model access through `crux-providers`
- Ollama-compatible local models as the default profile
- Deterministic controller around non-deterministic model output
- Schema-validated intermediate artifacts
- Bounded retries and refinement loops
- Run manifests for replay and inspection
- Scoped context provider boundary
- Memory candidate emission for external memory modules
- Reasoning-improvement benchmarks
- CLI first, minimal local web UI later

## What Axia is not

Axia is not model training software or durable memory software. It does not fine-tune, update weights, run LoRA jobs, perform reinforcement learning, own long-term user memory, or claim that a small model has become generally intelligent.

The product claim is narrower and stronger:

> Axia improves small-model results by reasoning decomposition, typed artifacts, validation, scoring, bounded repair, selective context assembly, and trace-grounded synthesis.

## Planned MVP commands

```bash
axia ask "Explain this problem"
axia run task.yaml
axia trace <run-id>
axia replay <run-id>
axia profiles list
axia benchmark run --suite baseline
```

## Project materials

```text
AGENTS.md                         Agent working rules
ARCHITECTURE_STANDARDS.md         Axia-specific architecture standards
ADRs/                             Architecture decision records
docs/SPEC-1.md                    Reasoning-first MVP clarification
docs/axia_spec.md                 Detailed Axia specification
docs/archive/                     Reference reports and original inspiration material
```

## Development direction

The first implementation should stay small: one CLI path, one local model profile, one deterministic fake provider for tests, one run store, one standard reasoning graph, and one reasoning-improvement benchmark against a single-shot baseline. Add complexity only after the trace proves the simple path works.
