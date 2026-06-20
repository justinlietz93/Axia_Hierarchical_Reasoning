from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.formation.canonical_request import CanonicalRequest
from axia.shared.errors import AxiaError
from axia.shared.ids import stable_json_hash


@dataclass(frozen=True)
class QualityCriterion:
    """One explicit acceptance dimension for a task constitution."""

    dimension: str
    weight: float
    threshold: float

    def __post_init__(self) -> None:
        if not self.dimension.strip():
            raise TaskConstitutionFailure(
                kind="task_constitution_invalid_rubric",
                message="rubric dimensions must be non-empty",
            )
        if self.weight <= 0:
            raise TaskConstitutionFailure(
                kind="task_constitution_invalid_rubric",
                message="rubric weights must be greater than zero",
            )
        if not 0 < self.threshold <= 1:
            raise TaskConstitutionFailure(
                kind="task_constitution_invalid_rubric",
                message="rubric thresholds must be within (0, 1]",
            )


@dataclass(frozen=True)
class ConstitutionLimits:
    """Declared limits that must exist before graph or refinement work begins."""

    max_depth: int
    max_model_calls: int
    max_retries_per_node: int
    max_seconds: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("max_depth", self.max_depth),
            ("max_model_calls", self.max_model_calls),
            ("max_retries_per_node", self.max_retries_per_node),
            ("max_seconds", self.max_seconds),
        ):
            if value <= 0:
                raise TaskConstitutionFailure(
                    kind="task_constitution_invalid_limits",
                    message=f"{field_name} must be greater than zero",
                )


DEFAULT_LIMITS: Mapping[str, ConstitutionLimits] = {
    "brief": ConstitutionLimits(max_depth=2, max_model_calls=6, max_retries_per_node=1, max_seconds=60),
    "standard": ConstitutionLimits(max_depth=4, max_model_calls=16, max_retries_per_node=2, max_seconds=300),
    "deep": ConstitutionLimits(max_depth=6, max_model_calls=40, max_retries_per_node=2, max_seconds=900),
}


@dataclass(frozen=True)
class TaskConstitution:
    """Immutable run-level contract required before a work graph may be formed."""

    revision: int
    previous_revision_hash: str | None
    source_request_hash: str
    canonical_request_hash: str
    mission: str
    deliverable_definition: str
    deliverable_type: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    required_evidence: tuple[str, ...]
    quality_rubric: tuple[QualityCriterion, ...]
    stop_conditions: tuple[str, ...]
    limits: ConstitutionLimits

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise TaskConstitutionFailure(
                kind="task_constitution_invalid_revision",
                message="constitution revisions start at one",
            )
        if self.revision == 1 and self.previous_revision_hash is not None:
            raise TaskConstitutionFailure(
                kind="task_constitution_invalid_revision",
                message="the initial constitution must not reference a previous revision",
            )
        if self.revision > 1 and not self.previous_revision_hash:
            raise TaskConstitutionFailure(
                kind="task_constitution_invalid_revision",
                message="a revised constitution must reference the previous revision",
            )
        for field_name, value in (
            ("source_request_hash", self.source_request_hash),
            ("canonical_request_hash", self.canonical_request_hash),
            ("mission", self.mission),
            ("deliverable_definition", self.deliverable_definition),
            ("deliverable_type", self.deliverable_type),
        ):
            if not value.strip():
                raise TaskConstitutionFailure(
                    kind="task_constitution_missing_required_value",
                    message=f"{field_name} must be non-empty",
                )
        for field_name, values in (
            ("non_goals", self.non_goals),
            ("allowed_operations", self.allowed_operations),
            ("required_evidence", self.required_evidence),
            ("quality_rubric", self.quality_rubric),
            ("stop_conditions", self.stop_conditions),
        ):
            if not values:
                raise TaskConstitutionFailure(
                    kind="task_constitution_missing_required_value",
                    message=f"{field_name} must not be empty",
                )

    def revision_hash(self) -> str:
        return stable_json_hash(self.to_payload())

    def to_payload(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "previous_revision_hash": self.previous_revision_hash,
            "source_request_hash": self.source_request_hash,
            "canonical_request_hash": self.canonical_request_hash,
            "mission": self.mission,
            "deliverable_definition": self.deliverable_definition,
            "deliverable_type": self.deliverable_type,
            "constraints": list(self.constraints),
            "non_goals": list(self.non_goals),
            "allowed_operations": list(self.allowed_operations),
            "required_evidence": list(self.required_evidence),
            "quality_rubric": [
                {
                    "dimension": criterion.dimension,
                    "weight": criterion.weight,
                    "threshold": criterion.threshold,
                }
                for criterion in self.quality_rubric
            ],
            "stop_conditions": list(self.stop_conditions),
            "max_depth": self.limits.max_depth,
            "max_model_calls": self.limits.max_model_calls,
            "max_retries_per_node": self.limits.max_retries_per_node,
            "max_seconds": self.limits.max_seconds,
        }


@dataclass(frozen=True)
class TaskConstitutionFailure(AxiaError):
    """A deterministic failure when the run contract is incomplete or invalid."""


def build_task_constitution(
    canonical_request: CanonicalRequest,
    *,
    limits: ConstitutionLimits | None = None,
    previous: TaskConstitution | None = None,
) -> TaskConstitution:
    """Form an immutable task contract from one canonical request and declared limits."""

    selected_limits = limits or DEFAULT_LIMITS[canonical_request.expected_depth]
    previous_revision_hash = previous.revision_hash() if previous is not None else None
    revision = previous.revision + 1 if previous is not None else 1
    if previous is not None and previous.source_request_hash != canonical_request.source_request_hash:
        raise TaskConstitutionFailure(
            kind="task_constitution_revision_source_mismatch",
            message="a revised constitution must derive from the same source request",
        )

    required_evidence = canonical_request.needed_context or ("accepted reasoning artifacts",)
    allowed_operations = ("context_provider",) if canonical_request.needed_context else ("none",)
    return TaskConstitution(
        revision=revision,
        previous_revision_hash=previous_revision_hash,
        source_request_hash=canonical_request.source_request_hash,
        canonical_request_hash=stable_json_hash(canonical_request.to_payload()),
        mission=canonical_request.intent,
        deliverable_definition=f"{canonical_request.deliverable_type}: {canonical_request.output_format}",
        deliverable_type=canonical_request.deliverable_type,
        constraints=canonical_request.constraints,
        non_goals=(
            "Do not treat unresolved unknowns as established facts.",
            "Do not exceed declared run limits.",
        ),
        allowed_operations=allowed_operations,
        required_evidence=required_evidence,
        quality_rubric=(
            QualityCriterion("constraint compliance", weight=1.0, threshold=0.82),
            QualityCriterion("completeness", weight=1.0, threshold=0.82),
            QualityCriterion("final usability", weight=1.0, threshold=0.82),
        ),
        stop_conditions=(
            "Accepted artifacts meet every required rubric threshold.",
            "Maximum recursion depth is reached.",
            "Maximum model-call budget is reached.",
            "Maximum wall-clock budget is reached.",
            "Retry budget is exhausted.",
            "Required clarification remains unresolved.",
        ),
        limits=selected_limits,
    )


def require_task_constitution(constitution: TaskConstitution | None) -> TaskConstitution:
    """Guard the future work-graph boundary against planning without a contract."""

    if constitution is None:
        raise TaskConstitutionFailure(
            kind="task_constitution_required",
            message="a work graph requires an explicit task constitution",
        )
    return constitution


def require_refinement_limits(constitution: TaskConstitution | None) -> ConstitutionLimits:
    """Guard future critique and repair operations against undeclared limits."""

    return require_task_constitution(constitution).limits
