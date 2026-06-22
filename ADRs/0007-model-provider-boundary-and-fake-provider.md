# ADR-0007: Model Provider Boundary And Deterministic Fake Provider

## Status

Accepted

## Context

Axia should be local-first and provider-agnostic. The project materials identify `crux-providers` as the expected provider stack for the standalone local profile, with local Ollama-compatible models as the default profile. Core reasoning must not be tied to one provider's HTTP shape, SDK objects, lifecycle, or failure semantics.

## Decision

Axia admits a model provider boundary as a core boundary feature.

The core reasoning path depends on an Axia-native `ModelProvider` port. Concrete provider adapters live at the boundary.

`crux-providers` is an optional boundary adapter dependency, not an Axia core dependency. The standalone CLI or local server composition root may instantiate a Crux-backed adapter. A host application that already uses Crux may inject its existing Crux-backed adapter into Axia. Axia must not create a hidden second Crux stack when the host already owns one.

Axia must also include a deterministic fake provider for tests. The fake provider must exercise controller behavior, including:

- prompt compilation;
- schema-shaped responses;
- malformed JSON;
- schema mismatch;
- timeout-like failures;
- retry and repair paths;
- scoring and manifest capture.

## Evidence

- `README.md` lists provider-agnostic access through an Axia-native `ModelProvider` port.
- `docs/axia_spec.md` requires the Axia controller to receive provider dependencies through injection.
- `ARCHITECTURE_STANDARDS.md` defines model provider boundary rules.

## Invariants Involved

- Provider-specific behavior must not enter core reasoning structures.
- Core reasoning modules must not import `crux-providers`.
- Provider errors must be translated at the boundary.
- Crux request and response objects must be translated into Axia-native request, response, metadata, and error records.
- Tests must validate controller logic without requiring a live model or network.

## Alternatives Rejected

### Implement an Ollama client inside Axia core

Rejected because it would bind core reasoning to a provider-specific boundary.

### Let provider response shapes become internal artifacts

Rejected because provider models must be translated into Axia-native records.

### Use trivial mocks only

Rejected because trivial mocks do not exercise parsing, retries, repair, scoring, or manifest behavior.

## Consequences

Axia can use different providers and can test controller behavior offline. Applications that already use Crux can compose Axia without duplicating provider ownership. The tradeoff is maintaining a clear adapter contract and fake-provider behavior that remains representative.

## Review Trigger

Review this decision if `crux-providers` no longer exposes the needed capabilities or if the suite adopts a shared provider boundary module.
