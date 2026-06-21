from __future__ import annotations

import json

from axia.boundary.ports.model_provider import ModelMessage, ModelProvider, ModelRequest
from axia.formation.canonical_request import (
    CANONICAL_REQUEST_SCHEMA,
    CanonicalRequest,
    EXPECTED_DEPTHS,
    canonical_request_from_json,
    canonical_request_from_payload,
)
from axia.source.records import RequestRecord
from axia.shared.ids import stable_json_hash


def build_canonical_request(
    raw_request: RequestRecord,
    provider: ModelProvider,
) -> CanonicalRequest:
    """Use a schema-constrained intake call, then apply deterministic validation."""

    response = provider.generate(compile_canonical_request_request(raw_request))
    return parse_canonical_request_response(raw_request, response.text)


def compile_canonical_request_request(
    raw_request: RequestRecord,
    *,
    validation_feedback: str | None = None,
) -> ModelRequest:
    """Compile the intake exchange so run control can preserve its exact prompt evidence."""

    prompt_parts = [
        "You are Axia's intake operator. Return only JSON matching the output schema. "
        "Make ambiguity explicit through unknowns and risk_flags; do not plan or solve the task.",
        "OUTPUT_SCHEMA\n" + json.dumps(CANONICAL_REQUEST_SCHEMA, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
    ]
    if validation_feedback is not None:
        prompt_parts.append(
            "PREVIOUS_OUTPUT_REJECTED\n"
            + validation_feedback
            + "\nReturn a new JSON object with every required field and no extra fields."
        )
    prompt = "\n\n".join(prompt_parts)
    return ModelRequest(
        messages=(
            ModelMessage(
                role="system",
                content=prompt,
            ),
            ModelMessage(role="user", content=raw_request.raw_text),
        ),
        output_schema=CANONICAL_REQUEST_SCHEMA,
        metadata={
            "stage": "canonical_request",
            "source_request_hash": raw_request.content_hash,
            "schema_hash": _schema_hash(),
            "prompt_hash": stable_json_hash(
                {
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": raw_request.raw_text},
                    ],
                    "output_schema": CANONICAL_REQUEST_SCHEMA,
                }
            ),
        },
    )


def parse_canonical_request_response(raw_request: RequestRecord, response_text: str) -> CanonicalRequest:
    """Validate one saved intake response without reissuing a provider call."""

    return canonical_request_from_json(raw_request, response_text)


def build_raw_request_fallback(raw_request: RequestRecord, *, expected_depth: str) -> CanonicalRequest:
    """Preserve a literal request when every bounded model intake attempt is rejected."""

    if expected_depth not in EXPECTED_DEPTHS:
        raise ValueError(f"expected_depth must be one of: {', '.join(sorted(EXPECTED_DEPTHS))}")
    return canonical_request_from_payload(
        raw_request,
        {
            "intent": raw_request.raw_text.strip(),
            "deliverable_type": "direct response",
            "constraints": [],
            "unknowns": ["Model-based intake was unavailable; the request is preserved literally."],
            "risk_flags": ["The canonical request uses a deterministic raw-request fallback."],
            "output_format": "concise response",
            "expected_depth": expected_depth,
            "needed_context": [],
        },
    )


def _schema_hash() -> str:
    return stable_json_hash(CANONICAL_REQUEST_SCHEMA)
