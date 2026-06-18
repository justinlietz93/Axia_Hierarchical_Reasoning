
![alt text](https://raw.githubusercontent.com/justinlietz93/Axia_Hierarchical_Reasoning/main/assets/axia_banner.png)

# Axia: Hierarchical Reasoning

Axia is a planned local-first LLM utility for improving small-model output through deterministic hierarchical reasoning. It treats the model as one narrow semantic operator inside a controlled system, not as the whole system.

The goal is simple: break a hard request into smaller validated steps, preserve the intermediate artifacts, score the work, repair weak outputs, and synthesize a final answer from an auditable trace.

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
  -> store trace and memory
```

## Intended properties

- Local-first by default
- Provider-agnostic model access through `crux-providers`
- Ollama-compatible local models as the default profile
- Deterministic controller around non-deterministic model output
- Schema-validated intermediate artifacts
- Bounded retries and refinement loops
- Run manifests for replay and inspection
- Local memory and retrieval
- CLI first, minimal local web UI later

## What Axia is not

Axia is not model training software. It does not fine-tune, update weights, run LoRA jobs, perform reinforcement learning, or claim that a small model has become generally intelligent.

The product claim is narrower and stronger:

> Axia improves small-model results by orchestration, validation, memory, critique, repair, and synthesis.

## Planned MVP commands

```bash
axia ask "Explain this problem"
axia run task.yaml
axia trace <run-id>
axia replay <run-id>
axia profiles list
axia memory search "query"
```

## Project materials

```text
AGENTS.md                         Agent working rules
EMERGENCE_BASED_ARCHITECTURE.md   Architecture philosophy and template
specs/inspiration_docs/           Source material and Axia specification
```

## Development direction

The first implementation should stay small: one CLI path, one local model profile, one deterministic fake provider for tests, one run store, and one standard reasoning graph. Add complexity only after the trace proves the simple path works.
