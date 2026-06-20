from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from axia.formation.context_pack import ContextPack
from axia.formation.work_graph import WorkNode
from axia.shared.errors import AxiaError
from axia.shared.ids import stable_json_hash


@dataclass(frozen=True)
class TypedArtifact:
    """A schema-validated JSON object admitted for deterministic evaluation."""

    payload: Mapping[str, object]
    content_hash: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> TypedArtifact:
        copied_payload = dict(payload)
        return cls(payload=copied_payload, content_hash=stable_json_hash(copied_payload))


@dataclass(frozen=True)
class MicroAgentEvaluation:
    """An evaluator result that the later controller may use for a policy decision."""

    accepted: bool
    reasons: tuple[str, ...]


class ArtifactEvaluator(Protocol):
    def evaluate(self, artifact: TypedArtifact) -> MicroAgentEvaluation:
        """Evaluate one typed artifact without provider access or ambient context."""


@dataclass(frozen=True)
class MicroAgentContract:
    """One narrow model role bound to a work-node schema and evaluator."""

    node: WorkNode
    role_prompt: str
    output_schema: Mapping[str, object]
    evaluator: ArtifactEvaluator

    def __post_init__(self) -> None:
        if not self.role_prompt.strip():
            raise MicroAgentFailure(
                kind="micro_agent_missing_role_prompt",
                message="a micro-agent contract requires a narrow role prompt",
            )
        if dict(self.output_schema) != dict(self.node.output_schema):
            raise MicroAgentFailure(
                kind="micro_agent_output_schema_mismatch",
                message="the micro-agent output schema must match its work node",
            )


@dataclass(frozen=True)
class MicroAgentFailure(AxiaError):
    """A deterministic failure while compiling or parsing one micro-agent exchange."""


def validate_context_pack(contract: MicroAgentContract, context_pack: ContextPack) -> dict[str, object]:
    """Admit only the context pack formed for the contract's exact work node."""

    if context_pack.node_id != contract.node.node_id:
        raise MicroAgentFailure(
            kind="micro_agent_context_node_mismatch",
            message="a micro-agent may use only a context pack for its own node",
        )
    if context_pack.node_instruction != contract.role_prompt.strip():
        raise MicroAgentFailure(
            kind="micro_agent_context_instruction_mismatch",
            message="the context pack instruction must match the micro-agent role prompt",
        )
    if dict(context_pack.output_schema) != dict(contract.output_schema):
        raise MicroAgentFailure(
            kind="micro_agent_context_schema_mismatch",
            message="the context pack output schema must match the micro-agent contract",
        )

    expected_fields = set(contract.node.context_scope)
    prompt_inputs = context_pack.prompt_inputs()
    supplied_fields = set(prompt_inputs)
    missing_fields = expected_fields - supplied_fields
    if missing_fields:
        raise MicroAgentFailure(
            kind="micro_agent_context_missing_fields",
            message=f"context pack is missing: {', '.join(sorted(missing_fields))}",
        )
    unexpected_fields = supplied_fields - expected_fields
    if unexpected_fields:
        raise MicroAgentFailure(
            kind="micro_agent_context_scope_violation",
            message=f"context pack includes undeclared fields: {', '.join(sorted(unexpected_fields))}",
        )
    return {field: prompt_inputs[field] for field in contract.node.context_scope}


def validate_typed_payload(payload: object, schema: Mapping[str, object]) -> Mapping[str, object]:
    """Validate the JSON object shape needed before evaluator or controller use."""

    _validate_schema_value(payload, schema, "$", MicroAgentFailure)
    if not isinstance(payload, Mapping):
        raise MicroAgentFailure(
            kind="micro_agent_output_schema_invalid",
            message="the output schema must admit an object",
        )
    return payload


def _validate_schema_value(
    value: object,
    schema: Mapping[str, object],
    path: str,
    failure_type: type[MicroAgentFailure],
) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_json_type(value, expected_type):
        raise failure_type(
            kind="micro_agent_output_schema_invalid",
            message=f"{path} must have JSON type {expected_type!r}",
        )
    if "enum" in schema and value not in schema["enum"]:
        raise failure_type(
            kind="micro_agent_output_schema_invalid",
            message=f"{path} must match one of the declared enum values",
        )
    if not isinstance(value, Mapping):
        return

    required_fields = schema.get("required", ())
    if not isinstance(required_fields, list):
        raise failure_type(
            kind="micro_agent_schema_invalid",
            message="schema required must be a list",
        )
    missing_fields = [field for field in required_fields if not isinstance(field, str) or field not in value]
    if missing_fields:
        raise failure_type(
            kind="micro_agent_output_schema_invalid",
            message=f"{path} is missing fields: {', '.join(str(field) for field in missing_fields)}",
        )

    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise failure_type(
            kind="micro_agent_schema_invalid",
            message="schema properties must be an object",
        )
    unexpected_fields = set(value) - set(properties)
    if schema.get("additionalProperties") is False and unexpected_fields:
        raise failure_type(
            kind="micro_agent_output_schema_invalid",
            message=f"{path} has unsupported fields: {', '.join(sorted(str(field) for field in unexpected_fields))}",
        )
    for field, field_schema in properties.items():
        if field in value:
            if not isinstance(field_schema, Mapping):
                raise failure_type(
                    kind="micro_agent_schema_invalid",
                    message=f"schema for {field!r} must be an object",
                )
            _validate_schema_value(value[field], field_schema, f"{path}.{field}", failure_type)


def _matches_json_type(value: object, expected_type: object) -> bool:
    matches = {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    return isinstance(expected_type, str) and matches.get(expected_type, False)
