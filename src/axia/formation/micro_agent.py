from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from axia.formation.context_pack import ContextPack
from axia.formation.structured_output import (
    StructuredOutputResult,
    ValidationIssue,
    parse_and_validate_json_object,
    validate_json_schema,
)
from axia.formation.work_graph import WorkNode
from axia.shared.errors import AxiaError
from axia.shared.ids import NodeId, stable_json_hash


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

    validation_errors: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class NodeValidationResult:
    """The parse and schema evidence retained for one node output attempt."""

    node_id: NodeId
    artifact: TypedArtifact | None
    validation_errors: tuple[ValidationIssue, ...]

    @property
    def accepted(self) -> bool:
        return self.artifact is not None and not self.validation_errors


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

    validation_errors = validate_json_schema(payload, schema)
    if validation_errors:
        issue = validation_errors[0]
        raise MicroAgentFailure(
            kind="micro_agent_output_schema_invalid",
            message=f"{issue.path} {issue.message}",
            validation_errors=validation_errors,
        )
    if not isinstance(payload, Mapping):
        raise MicroAgentFailure(
            kind="micro_agent_output_schema_invalid",
            message="the output schema must admit an object",
        )
    return payload


def validate_micro_agent_response(contract: MicroAgentContract, response_text: str) -> NodeValidationResult:
    """Retain parse and schema errors in a node result before controller policy acts."""

    parsed_output: StructuredOutputResult = parse_and_validate_json_object(response_text, contract.output_schema)
    if not parsed_output.accepted:
        return NodeValidationResult(
            node_id=contract.node.node_id,
            artifact=None,
            validation_errors=parsed_output.validation_errors,
        )
    assert parsed_output.payload is not None
    return NodeValidationResult(
        node_id=contract.node.node_id,
        artifact=TypedArtifact.from_payload(parsed_output.payload),
        validation_errors=(),
    )


def require_valid_node_output(node_result: NodeValidationResult) -> TypedArtifact:
    """Prevent evaluator or controller use of a node output with parse or schema errors."""

    if node_result.accepted:
        assert node_result.artifact is not None
        return node_result.artifact
    issue = node_result.validation_errors[0]
    if issue.rule == "json_parse":
        kind = "micro_agent_output_json_invalid"
    elif issue.rule == "schema":
        kind = "micro_agent_schema_invalid"
    else:
        kind = "micro_agent_output_schema_invalid"
    raise MicroAgentFailure(
        kind=kind,
        message=f"{issue.path} {issue.message}",
        validation_errors=node_result.validation_errors,
    )
