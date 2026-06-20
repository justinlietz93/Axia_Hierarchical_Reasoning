from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from axia.shared.errors import AxiaError
from axia.source.records import RequestRecord


CANONICAL_REQUEST_FIELDS = frozenset(
    {
        "intent",
        "deliverable_type",
        "constraints",
        "unknowns",
        "risk_flags",
        "output_format",
        "expected_depth",
        "needed_context",
    }
)
EXPECTED_DEPTHS = frozenset({"brief", "standard", "deep"})
CANONICAL_REQUEST_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": sorted(CANONICAL_REQUEST_FIELDS),
    "properties": {
        "intent": {"type": "string", "minLength": 1},
        "deliverable_type": {"type": "string", "minLength": 1},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "output_format": {"type": "string", "minLength": 1},
        "expected_depth": {"type": "string", "enum": sorted(EXPECTED_DEPTHS)},
        "needed_context": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass(frozen=True)
class CanonicalRequest:
    """An explicit, validated interpretation of one raw user request."""

    source_request_hash: str
    intent: str
    deliverable_type: str
    constraints: tuple[str, ...]
    unknowns: tuple[str, ...]
    risk_flags: tuple[str, ...]
    output_format: str
    expected_depth: str
    needed_context: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "deliverable_type": self.deliverable_type,
            "constraints": list(self.constraints),
            "unknowns": list(self.unknowns),
            "risk_flags": list(self.risk_flags),
            "output_format": self.output_format,
            "expected_depth": self.expected_depth,
            "needed_context": list(self.needed_context),
        }


@dataclass(frozen=True)
class CanonicalRequestFailure(AxiaError):
    """A deterministic canonical-request formation failure."""


def canonical_request_from_json(raw_request: RequestRecord, text: str) -> CanonicalRequest:
    """Parse a schema-shaped model result into an Axia-native canonical request."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise CanonicalRequestFailure(
            kind="canonical_request_json_invalid",
            message="canonical request output must be valid JSON",
        ) from error
    if not isinstance(payload, Mapping):
        raise CanonicalRequestFailure(
            kind="canonical_request_schema_invalid",
            message="canonical request output must be a JSON object",
        )
    return canonical_request_from_payload(raw_request, payload)


def canonical_request_from_payload(
    raw_request: RequestRecord,
    payload: Mapping[str, object],
) -> CanonicalRequest:
    """Validate a canonical request without calling a provider or doing IO."""

    if not raw_request.raw_text.strip():
        raise CanonicalRequestFailure(
            kind="canonical_request_missing_raw_text",
            message="a canonical request requires non-empty user text",
        )

    payload_fields = set(payload)
    missing_fields = CANONICAL_REQUEST_FIELDS - payload_fields
    if missing_fields:
        raise CanonicalRequestFailure(
            kind="canonical_request_missing_fields",
            message=f"canonical request is missing: {', '.join(sorted(missing_fields))}",
        )
    unexpected_fields = payload_fields - CANONICAL_REQUEST_FIELDS
    if unexpected_fields:
        raise CanonicalRequestFailure(
            kind="canonical_request_unknown_fields",
            message=f"canonical request has unsupported fields: {', '.join(sorted(unexpected_fields))}",
        )

    expected_depth = _required_text(payload, "expected_depth")
    if expected_depth not in EXPECTED_DEPTHS:
        raise CanonicalRequestFailure(
            kind="canonical_request_invalid_depth",
            message=f"expected_depth must be one of: {', '.join(sorted(EXPECTED_DEPTHS))}",
        )

    return CanonicalRequest(
        source_request_hash=raw_request.content_hash,
        intent=_required_text(payload, "intent"),
        deliverable_type=_required_text(payload, "deliverable_type"),
        constraints=_text_collection(payload, "constraints"),
        unknowns=_text_collection(payload, "unknowns"),
        risk_flags=_text_collection(payload, "risk_flags"),
        output_format=_required_text(payload, "output_format"),
        expected_depth=expected_depth,
        needed_context=_text_collection(payload, "needed_context"),
    )


def _required_text(payload: Mapping[str, object], field_name: str) -> str:
    value = payload[field_name]
    if not isinstance(value, str) or not value.strip():
        raise CanonicalRequestFailure(
            kind="canonical_request_invalid_text",
            message=f"{field_name} must be a non-empty string",
        )
    return value.strip()


def _text_collection(payload: Mapping[str, object], field_name: str) -> tuple[str, ...]:
    value = payload[field_name]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise CanonicalRequestFailure(
            kind="canonical_request_invalid_collection",
            message=f"{field_name} must be a list of non-empty strings",
        )
    return tuple(item.strip() for item in value)
