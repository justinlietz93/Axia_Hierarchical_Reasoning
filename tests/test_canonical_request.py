from __future__ import annotations

import json
import unittest

from axia.boundary.ports.model_provider import ModelRequest, ModelResponse
from axia.formation.canonical_request import (
    CANONICAL_REQUEST_SCHEMA,
    CanonicalRequestFailure,
    canonical_request_from_payload,
)
from axia.operation import build_canonical_request
from axia.source import RequestRecord


class StaticProvider:
    def __init__(self, text: str) -> None:
        self.text = text
        self.request: ModelRequest | None = None

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.request = request
        return ModelResponse(text=self.text, metadata={"provider": "test"})


def _valid_payload() -> dict[str, object]:
    return {
        "intent": "compare database options",
        "deliverable_type": "technical recommendation",
        "constraints": ["local-first", "practical tradeoffs"],
        "unknowns": ["expected data volume"],
        "risk_flags": ["recommendation depends on scale"],
        "output_format": "concise comparison with recommendation",
        "expected_depth": "standard",
        "needed_context": ["project architecture", "storage needs"],
    }


class CanonicalRequestTests(unittest.TestCase):
    def test_schema_constrained_intake_preserves_source_identity(self) -> None:
        raw_request = RequestRecord.from_text("Compare local databases for this AI tool")
        provider = StaticProvider(json.dumps(_valid_payload()))

        canonical = build_canonical_request(raw_request, provider)

        assert provider.request is not None
        self.assertEqual(provider.request.output_schema, CANONICAL_REQUEST_SCHEMA)
        self.assertEqual(provider.request.metadata["stage"], "canonical_request")
        self.assertEqual(provider.request.metadata["source_request_hash"], raw_request.content_hash)
        self.assertEqual(canonical.source_request_hash, raw_request.content_hash)
        self.assertEqual(canonical.intent, "compare database options")
        self.assertEqual(canonical.needed_context, ("project architecture", "storage needs"))

    def test_rejects_malformed_intake_json(self) -> None:
        provider = StaticProvider("{")
        with self.assertRaises(CanonicalRequestFailure) as failure:
            build_canonical_request(RequestRecord.from_text("help me compare options"), provider)

        self.assertEqual(failure.exception.kind, "canonical_request_json_invalid")

    def test_rejects_underspecified_intake_payload(self) -> None:
        payload = _valid_payload()
        del payload["unknowns"]
        with self.assertRaises(CanonicalRequestFailure) as failure:
            canonical_request_from_payload(RequestRecord.from_text("Help me decide"), payload)

        self.assertEqual(failure.exception.kind, "canonical_request_missing_fields")

    def test_rejects_invalid_depth_and_ambiguous_blank_intent(self) -> None:
        invalid_depth = _valid_payload()
        invalid_depth["expected_depth"] = "unbounded"
        with self.assertRaises(CanonicalRequestFailure) as depth_failure:
            canonical_request_from_payload(RequestRecord.from_text("Explain a protocol"), invalid_depth)

        ambiguous_intent = _valid_payload()
        ambiguous_intent["intent"] = "  "
        with self.assertRaises(CanonicalRequestFailure) as intent_failure:
            canonical_request_from_payload(RequestRecord.from_text("Help"), ambiguous_intent)

        self.assertEqual(depth_failure.exception.kind, "canonical_request_invalid_depth")
        self.assertEqual(intent_failure.exception.kind, "canonical_request_invalid_text")

    def test_rejects_empty_raw_request_before_interpretation(self) -> None:
        with self.assertRaises(CanonicalRequestFailure) as failure:
            canonical_request_from_payload(RequestRecord.from_text("  "), _valid_payload())

        self.assertEqual(failure.exception.kind, "canonical_request_missing_raw_text")


if __name__ == "__main__":
    unittest.main()
