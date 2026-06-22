from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.shared.errors import AxiaError
from axia.shared.ids import stable_json_hash


@dataclass(frozen=True)
class ModelProfile:
    """A named, reproducible local-model configuration selected at composition time."""

    name: str
    provider: str
    model: str
    host: str
    context_window_tokens: int
    max_output_tokens: int
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    seed: int
    json_mode: str
    timeout_seconds: int
    retry_attempts: int
    stop_sequences: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name, value in (
            ("name", self.name),
            ("provider", self.provider),
            ("model", self.model),
            ("host", self.host),
            ("json_mode", self.json_mode),
        ):
            if not value.strip():
                raise ModelProfileFailure(
                    kind="model_profile_required_value_missing",
                    message=f"{field_name} must be non-empty",
                )
        if self.context_window_tokens <= 0 or self.max_output_tokens <= 0:
            raise ModelProfileFailure(
                kind="model_profile_token_limit_invalid",
                message="context_window_tokens and max_output_tokens must be greater than zero",
            )
        if not 0 <= self.temperature <= 2 or not 0 < self.top_p <= 1:
            raise ModelProfileFailure(
                kind="model_profile_sampling_invalid",
                message="temperature must be within [0, 2] and top_p must be within (0, 1]",
            )
        if self.top_k <= 0 or self.repeat_penalty <= 0:
            raise ModelProfileFailure(
                kind="model_profile_sampling_invalid",
                message="top_k and repeat_penalty must be greater than zero",
            )
        if self.timeout_seconds <= 0 or self.retry_attempts < 0:
            raise ModelProfileFailure(
                kind="model_profile_execution_invalid",
                message="timeout_seconds must be positive and retry_attempts must not be negative",
            )
        if self.json_mode not in {"preferred", "required", "off"}:
            raise ModelProfileFailure(
                kind="model_profile_json_mode_invalid",
                message="json_mode must be preferred, required, or off",
            )
        if any(not sequence.strip() for sequence in self.stop_sequences):
            raise ModelProfileFailure(
                kind="model_profile_stop_sequence_invalid",
                message="stop_sequences must not contain blank values",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "host": self.host,
            "context_window_tokens": self.context_window_tokens,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "seed": self.seed,
            "json_mode": self.json_mode,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_attempts,
            "stop_sequences": list(self.stop_sequences),
        }

    def profile_hash(self) -> str:
        return stable_json_hash(self.to_payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ModelProfile":
        required = {
            "name",
            "provider",
            "model",
            "host",
            "context_window_tokens",
            "max_output_tokens",
            "temperature",
            "top_p",
            "top_k",
            "repeat_penalty",
            "seed",
            "json_mode",
            "timeout_seconds",
            "retry_attempts",
        }
        missing = required - set(payload)
        if missing:
            raise ModelProfileFailure(
                kind="model_profile_fields_missing",
                message=f"model profile is missing: {', '.join(sorted(missing))}",
            )
        unexpected = set(payload) - required - {"stop_sequences"}
        if unexpected:
            raise ModelProfileFailure(
                kind="model_profile_unknown_fields",
                message=f"model profile has unsupported fields: {', '.join(sorted(unexpected))}",
            )
        stop_sequences = payload.get("stop_sequences", [])
        if not isinstance(stop_sequences, list) or any(not isinstance(value, str) for value in stop_sequences):
            raise ModelProfileFailure(
                kind="model_profile_stop_sequence_invalid",
                message="stop_sequences must be a list of strings",
            )
        try:
            return cls(
                name=_text(payload, "name"),
                provider=_text(payload, "provider"),
                model=_text(payload, "model"),
                host=_text(payload, "host"),
                context_window_tokens=_integer(payload, "context_window_tokens"),
                max_output_tokens=_integer(payload, "max_output_tokens"),
                temperature=_number(payload, "temperature"),
                top_p=_number(payload, "top_p"),
                top_k=_integer(payload, "top_k"),
                repeat_penalty=_number(payload, "repeat_penalty"),
                seed=_integer(payload, "seed"),
                json_mode=_text(payload, "json_mode"),
                timeout_seconds=_integer(payload, "timeout_seconds"),
                retry_attempts=_integer(payload, "retry_attempts"),
                stop_sequences=tuple(stop_sequences),
            )
        except ModelProfileFailure:
            raise


@dataclass(frozen=True)
class ModelProfileFailure(AxiaError):
    """A profile shape or reproducibility requirement was not met."""


def _text(payload: Mapping[str, object], field_name: str) -> str:
    value = payload[field_name]
    if not isinstance(value, str):
        raise ModelProfileFailure(
            kind="model_profile_field_type_invalid",
            message=f"{field_name} must be a string",
        )
    return value


def _integer(payload: Mapping[str, object], field_name: str) -> int:
    value = payload[field_name]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ModelProfileFailure(
            kind="model_profile_field_type_invalid",
            message=f"{field_name} must be an integer",
        )
    return value


def _number(payload: Mapping[str, object], field_name: str) -> float:
    value = payload[field_name]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ModelProfileFailure(
            kind="model_profile_field_type_invalid",
            message=f"{field_name} must be a number",
        )
    return float(value)
