# SPEC-1-Axia-Hierarchical-Reasoning

## Background

Axia is a **reasoning orchestration tool**, not a memory product.

Its purpose is to make small or local LLMs perform better by decomposing complex reasoning into controlled stages: request interpretation, task framing, planning, agent role assignment, intermediate reasoning, critique, repair, scoring, and final synthesis.

Axia should not present “memory” as a user-facing feature. Any storage or retrieval exists only to support the reasoning process, such as:

```text
current task context
run-local artifacts
intermediate agent outputs
evidence packs
scratchpad summaries
trace replay data
bounded context reuse when needed
```

The system should feel like one reasoning assistant, while internally operating as a deterministic controller coordinating small specialized reasoning steps.

Axia must prioritize reasoning-improvement systems over memory, UI, or generic-agent breadth. The first implementation should prove that decomposition, typed artifacts, validation, scoring, bounded repair, and trace-grounded synthesis improve output over a single-shot small-model baseline.

## Requirements

### Must Have

* Axia must be framed as a **reasoning engine**, not a memory engine.
* Memory must only exist where required for context management, run tracing, and agentic reasoning.
* Every run must produce a structured reasoning trace.
* Context must be explicitly packed, scoped, and passed between reasoning stages.
* Agents must not share an implicit global memory.
* Any persisted data must be explainable as one of:

  * run trace
  * artifact cache
  * context index
  * evidence reference
  * replay/debug metadata
* The MVP must support reasoning decomposition into:

  * canonical request
  * task constitution
  * work graph
  * agent execution
  * critique
  * repair
  * synthesis
* Retrieval should be treated as **context assembly**, not personal memory.
* The system must support bounded reasoning loops.
* The controller must prevent unbounded recursive agent calls.
* The final output must be generated from validated intermediate artifacts.
* The MVP must include a reasoning-improvement benchmark against a single-shot baseline.

### Should Have

* Context budget manager.
* Evidence/context pack builder.
* Trace viewer for inspecting how reasoning unfolded.
* Run replay from stored artifacts.
* Optional summarization of intermediate reasoning artifacts for context compression.
* Verifier-style checks for support, constraint compliance, and repair effectiveness.

### Won’t Have in MVP

* User-facing “memory search” as a core feature.
* Long-term personal memory.
* Autonomous profile learning.
* Background memory accumulation.
* Chatbot-style persistent personality memory.
* Vector database as a primary product pillar.
* Claims that Axia “remembers” the user across tasks unless explicitly configured later.

## Clarifying Design Decision

My suggested assumption:

```text
Axia should persist traces and artifacts for observability/replay,
but should not persist reusable user memory by default.
```
