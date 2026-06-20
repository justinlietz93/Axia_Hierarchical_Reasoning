from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from axia.formation.task_constitution import TaskConstitution
from axia.formation.work_graph import WorkNode
from axia.shared.errors import AxiaError
from axia.shared.ids import NodeId, stable_json_hash


CONTEXT_REFERENCE_TYPES = frozenset({"request", "artifact", "evidence", "scorecard", "policy"})
CONTEXT_BUDGETS_BY_NODE_KIND: Mapping[str, int] = {
    "canonicalize": 4_800,
    "constitute": 6_400,
    "retrieve": 4_800,
    "plan": 7_200,
    "draft": 5_600,
    "critique": 6_400,
    "repair": 5_600,
    "verify": 6_400,
    "final": 9_600,
    "emit_memory_candidate": 5_600,
}
DEFAULT_CONTEXT_BUDGET = 6_400
CONSTITUTION_FIELDS_BY_NODE_KIND: Mapping[str, tuple[str, ...]] = {
    "retrieve": ("mission", "required_evidence", "allowed_operations"),
    "plan": (
        "mission",
        "deliverable_definition",
        "constraints",
        "non_goals",
        "required_evidence",
        "quality_rubric",
        "stop_conditions",
    ),
    "critique": ("mission", "deliverable_definition", "constraints", "non_goals", "quality_rubric"),
    "verify": ("mission", "deliverable_definition", "constraints", "quality_rubric"),
}
DEFAULT_CONSTITUTION_FIELDS = ("mission", "deliverable_definition", "constraints", "non_goals")


@dataclass(frozen=True)
class ContextReference:
    """One scoped, run-local input with preserved source identity."""

    scope: str
    source_type: str
    reference_id: str
    content: object
    content_hash: str
    accepted: bool = True

    def __post_init__(self) -> None:
        if not self.scope.strip() or not self.reference_id.strip() or not self.content_hash.strip():
            raise ContextPackFailure(
                kind="context_reference_missing_identity",
                message="context references require scope, reference ID, and content hash",
            )
        if self.source_type not in CONTEXT_REFERENCE_TYPES:
            raise ContextPackFailure(
                kind="context_reference_unknown_source_type",
                message=f"unsupported context reference source type {self.source_type!r}",
            )
        try:
            expected_content_hash = stable_json_hash(self.content)
        except TypeError as error:
            raise ContextPackFailure(
                kind="context_reference_non_json_content",
                message="context reference content must be JSON serializable",
            ) from error
        if self.content_hash != expected_content_hash:
            raise ContextPackFailure(
                kind="context_reference_content_hash_mismatch",
                message="context reference content hash must match its content",
            )

    @classmethod
    def from_content(
        cls,
        *,
        scope: str,
        source_type: str,
        reference_id: str,
        content: object,
        accepted: bool = True,
    ) -> ContextReference:
        try:
            content_hash = stable_json_hash(content)
        except TypeError as error:
            raise ContextPackFailure(
                kind="context_reference_non_json_content",
                message="context reference content must be JSON serializable",
            ) from error
        return cls(
            scope=scope,
            source_type=source_type,
            reference_id=reference_id,
            content=content,
            content_hash=content_hash,
            accepted=accepted,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "source_type": self.source_type,
            "reference_id": self.reference_id,
            "content": self.content,
            "content_hash": self.content_hash,
            "accepted": self.accepted,
        }


@dataclass(frozen=True)
class ContextPack:
    """The complete, bounded run-local input for one work node."""

    node_id: NodeId
    node_instruction: str
    constitution_subset: Mapping[str, object]
    references: tuple[ContextReference, ...]
    output_schema: Mapping[str, object]
    max_serialized_characters: int
    serialized_characters: int
    content_hash: str

    def __post_init__(self) -> None:
        if not self.node_instruction.strip():
            raise ContextPackFailure(
                kind="context_pack_missing_instruction",
                message="a context pack requires a node instruction",
            )
        if self.max_serialized_characters <= 0:
            raise ContextPackFailure(
                kind="context_pack_invalid_budget",
                message="a context pack budget must be greater than zero",
            )
        if self.serialized_characters > self.max_serialized_characters:
            raise ContextPackFailure(
                kind="context_pack_budget_exceeded",
                message="context pack exceeds its node budget",
            )
        if self.serialized_characters != len(_canonical_json(self.to_payload())):
            raise ContextPackFailure(
                kind="context_pack_serialization_mismatch",
                message="context pack serialized character count must match its payload",
            )
        if self.content_hash != stable_json_hash(self.to_payload()):
            raise ContextPackFailure(
                kind="context_pack_content_hash_mismatch",
                message="context pack content hash must match its payload",
            )

    def prompt_inputs(self) -> dict[str, object]:
        """Return only scoped node inputs, in deterministic reference order."""

        grouped_references: dict[str, list[object]] = {}
        for reference in self.references:
            grouped_references.setdefault(reference.scope, []).append(reference.content)

        inputs: dict[str, object] = {}
        if self.constitution_subset:
            inputs["constitution"] = dict(self.constitution_subset)
        for scope in sorted(grouped_references):
            values = grouped_references[scope]
            inputs[scope] = values[0] if len(values) == 1 else values
        return inputs

    def to_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id.value,
            "node_instruction": self.node_instruction,
            "constitution_subset": dict(self.constitution_subset),
            "references": [reference.to_payload() for reference in self.references],
            "output_schema": dict(self.output_schema),
            "max_serialized_characters": self.max_serialized_characters,
        }


@dataclass(frozen=True)
class ContextPackFailure(AxiaError):
    """A deterministic failure while forming a scoped run-local context pack."""


def build_context_pack(
    node: WorkNode,
    *,
    node_instruction: str,
    constitution: TaskConstitution,
    prior_artifacts: tuple[ContextReference, ...] = (),
    context_records: tuple[ContextReference, ...] = (),
    max_serialized_characters: int | None = None,
) -> ContextPack:
    """Form the exact context admitted by one node contract and its run inputs."""

    if not node_instruction.strip():
        raise ContextPackFailure(
            kind="context_pack_missing_instruction",
            message="a context pack requires a node instruction",
        )
    _validate_reference_sources(prior_artifacts, context_records)
    references = tuple(sorted((*prior_artifacts, *context_records), key=_reference_order))
    _validate_reference_scope(node, references)

    constitution_subset = _constitution_subset(node, constitution)
    actual_scopes = {reference.scope for reference in references}
    if constitution_subset:
        actual_scopes.add("constitution")
    missing_scopes = set(node.context_scope) - actual_scopes
    if missing_scopes:
        raise ContextPackFailure(
            kind="context_pack_missing_scope",
            message=f"context pack is missing scopes: {', '.join(sorted(missing_scopes))}",
        )

    budget = (
        CONTEXT_BUDGETS_BY_NODE_KIND.get(node.kind, DEFAULT_CONTEXT_BUDGET)
        if max_serialized_characters is None
        else max_serialized_characters
    )
    payload = {
        "node_id": node.node_id.value,
        "node_instruction": node_instruction.strip(),
        "constitution_subset": constitution_subset,
        "references": [reference.to_payload() for reference in references],
        "output_schema": dict(node.output_schema),
        "max_serialized_characters": budget,
    }
    serialized_characters = len(_canonical_json(payload))
    if serialized_characters > budget:
        raise ContextPackFailure(
            kind="context_pack_budget_exceeded",
            message=f"context pack requires {serialized_characters} characters but node budget is {budget}",
        )
    return ContextPack(
        node_id=node.node_id,
        node_instruction=node_instruction.strip(),
        constitution_subset=constitution_subset,
        references=references,
        output_schema=node.output_schema,
        max_serialized_characters=budget,
        serialized_characters=serialized_characters,
        content_hash=stable_json_hash(payload),
    )


def _validate_reference_sources(
    prior_artifacts: tuple[ContextReference, ...],
    context_records: tuple[ContextReference, ...],
) -> None:
    invalid_prior_sources = [
        reference.source_type
        for reference in prior_artifacts
        if reference.source_type not in {"request", "artifact", "scorecard", "policy"}
    ]
    if invalid_prior_sources:
        raise ContextPackFailure(
            kind="context_pack_invalid_prior_source",
            message="prior artifacts must be request or artifact references",
        )
    invalid_context_sources = [reference.source_type for reference in context_records if reference.source_type != "evidence"]
    if invalid_context_sources:
        raise ContextPackFailure(
            kind="context_pack_invalid_evidence_source",
            message="context records must be evidence references",
        )


def _validate_reference_scope(node: WorkNode, references: tuple[ContextReference, ...]) -> None:
    declared_scopes = set(node.context_scope)
    duplicate_references: set[tuple[str, str, str]] = set()
    duplicate_content: set[tuple[str, str]] = set()
    seen_references: set[tuple[str, str, str]] = set()
    seen_content: set[tuple[str, str]] = set()
    for reference in references:
        if reference.scope == "constitution":
            raise ContextPackFailure(
                kind="context_pack_scope_violation",
                message="constitution context may only come from the task constitution subset",
            )
        if reference.scope not in declared_scopes:
            raise ContextPackFailure(
                kind="context_pack_scope_violation",
                message=f"reference {reference.reference_id!r} is outside node context scope",
            )
        if reference.source_type == "artifact" and not reference.accepted and node.kind != "repair":
            raise ContextPackFailure(
                kind="context_pack_rejected_artifact",
                message="rejected artifacts may enter context only for repair",
            )
        reference_key = (reference.scope, reference.source_type, reference.reference_id)
        if reference_key in seen_references:
            duplicate_references.add(reference_key)
        seen_references.add(reference_key)
        content_key = (reference.scope, reference.content_hash)
        if content_key in seen_content:
            duplicate_content.add(content_key)
        seen_content.add(content_key)
    if duplicate_references or duplicate_content:
        raise ContextPackFailure(
            kind="context_pack_duplicate_reference",
            message="context pack references and content must be unique within a scope",
        )


def _constitution_subset(node: WorkNode, constitution: TaskConstitution) -> dict[str, object]:
    if "constitution" not in node.context_scope:
        return {}
    values: Mapping[str, object] = {
        "mission": constitution.mission,
        "deliverable_definition": constitution.deliverable_definition,
        "constraints": list(constitution.constraints),
        "non_goals": list(constitution.non_goals),
        "allowed_operations": list(constitution.allowed_operations),
        "required_evidence": list(constitution.required_evidence),
        "quality_rubric": [
            {
                "dimension": criterion.dimension,
                "weight": criterion.weight,
                "threshold": criterion.threshold,
            }
            for criterion in constitution.quality_rubric
        ],
        "stop_conditions": list(constitution.stop_conditions),
    }
    fields = CONSTITUTION_FIELDS_BY_NODE_KIND.get(node.kind, DEFAULT_CONSTITUTION_FIELDS)
    return {field: values[field] for field in fields}


def _reference_order(reference: ContextReference) -> tuple[str, str, str, str]:
    return (reference.scope, reference.source_type, reference.reference_id, reference.content_hash)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
