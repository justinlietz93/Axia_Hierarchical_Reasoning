from __future__ import annotations

from axia.boundary.ports.model_provider import ModelMessage, ModelProvider, ModelRequest
from axia.formation.canonical_request import (
    CANONICAL_REQUEST_SCHEMA,
    CanonicalRequest,
    canonical_request_from_json,
)
from axia.source.records import RequestRecord
from axia.shared.ids import stable_json_hash


def build_canonical_request(
    raw_request: RequestRecord,
    provider: ModelProvider,
) -> CanonicalRequest:
    """Use a schema-constrained intake call, then apply deterministic validation."""

    request = ModelRequest(
        messages=(
            ModelMessage(
                role="system",
                content=(
                    "You are Axia's intake operator. Return only JSON matching the output schema. "
                    "Make ambiguity explicit through unknowns and risk_flags; do not plan or solve the task."
                ),
            ),
            ModelMessage(role="user", content=raw_request.raw_text),
        ),
        output_schema=CANONICAL_REQUEST_SCHEMA,
        metadata={
            "stage": "canonical_request",
            "source_request_hash": raw_request.content_hash,
            "schema_hash": _schema_hash(),
        },
    )
    response = provider.generate(request)
    return canonical_request_from_json(raw_request, response.text)


def _schema_hash() -> str:
    return stable_json_hash(CANONICAL_REQUEST_SCHEMA)
