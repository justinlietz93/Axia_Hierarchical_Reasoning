from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from axia.boundary.ports.model_provider import (
    ModelRequest,
    ModelResponse,
    ProviderFailure,
)

FakeMode = Literal["valid", "malformed_json", "schema_mismatch", "empty", "timeout"]


@dataclass(frozen=True)
class FakeProvider:
    """Deterministic schema-aware provider for controller tests."""

    mode: FakeMode = "valid"
    request_id: str = "fake-123"
    response_id: str = "fake-456"

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self.mode == "timeout":
            raise ProviderFailure(
                kind="provider_timeout",
                message="fake provider timeout",
                retryable=True,
            )

        metadata = {
            "provider": "fake",
            "request_id": self.request_id,
            "response_id": self.response_id,
        }

        if self.mode == "malformed_json":
            return ModelResponse(text="{", metadata=metadata)
        if self.mode == "schema_mismatch":
            return ModelResponse(text='{"unexpected": true}', metadata=metadata)
        if self.mode == "empty":
            return ModelResponse(text="", metadata=metadata)

        return ModelResponse(text=self._valid_text(request), metadata=metadata)

    def _valid_text(self, request: ModelRequest) -> str:
        if request.output_schema is not None or "output_schema" in request.prompt_text():
            return '{"status": "ok", "value": "test"}'
        return '{"text": "fake response"}'


def fake_provider_from_config(config: Mapping[str, str] | None = None) -> FakeProvider:
    config = dict(config or {})
    mode = config.get("mode", "valid")
    if mode not in {"valid", "malformed_json", "schema_mismatch", "empty", "timeout"}:
        raise ValueError(f"unsupported fake provider mode: {mode}")
    return FakeProvider(mode=mode)  # type: ignore[arg-type]

