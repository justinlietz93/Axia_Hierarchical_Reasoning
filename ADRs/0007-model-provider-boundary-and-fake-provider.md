# ADR-0007: Model Provider Boundary And Deterministic Fake Provider

## Status

Accepted

## Context

Axia should be local-first and provider-agnostic. The project materials identify `crux-providers` as the model-access boundary, with local Ollama-compatible models as the default profile. Core reasoning must not be tied to one provider's HTTP shape or failure semantics.

## Decision

Axia admits a model provider boundary as a core boundary feature.

The core reasoning path depends on an Axia-native provider port. Concrete provider adapters live at the boundary. `crux-providers` is the expected model-access dependency unless a later decision supersedes it.

Axia must also include a deterministic fake provider for tests. The fake provider must exercise controller behavior, including:

- prompt compilation;
- schema-shaped responses;
- malformed JSON;
- schema mismatch;
- timeout-like failures;
- retry and repair paths;
- scoring and manifest capture.

## Evidence

- `README.md` lists provider-agnostic access through `crux-providers`.
- `docs/axia_spec.md` requires `crux-providers` as the sole LLM/provider dependency during MVP.
- `ARCHITECTURE_STANDARDS.md` defines model provider boundary rules.

## Invariants Involved

- Provider-specific behavior must not enter core reasoning structures.
- Provider errors must be translated at the boundary.
- Tests must validate controller logic without requiring a live model or network.

## Alternatives Rejected

### Implement an Ollama client inside Axia core

Rejected because it would bind core reasoning to a provider-specific boundary.

### Let provider response shapes become internal artifacts

Rejected because provider models must be translated into Axia-native records.

### Use trivial mocks only

Rejected because trivial mocks do not exercise parsing, retries, repair, scoring, or manifest behavior.

## Consequences

Axia can use different providers and can test controller behavior offline. The tradeoff is maintaining a clear adapter contract and fake-provider behavior that remains representative.

## Review Trigger

Review this decision if `crux-providers` no longer exposes the needed capabilities or if the suite adopts a shared provider boundary module.

