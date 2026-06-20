from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Mapping

from axia.formation.micro_agent import NodeValidationResult, TypedArtifact
from axia.formation.structured_output import parse_and_validate_json_object
from axia.formation.task_constitution import TaskConstitution
from axia.formation.work_graph import ScorePolicy, WorkNode
from axia.shared.errors import AxiaError
from axia.shared.ids import ArtifactId, NodeId, RunId, ScorecardId, stable_json_hash


SCORE_DIMENSIONS = (
    "relevance",
    "completeness",
    "consistency",
    "specificity",
    "evidence_use",
    "constraint_compliance",
    "final_usability",
)
SCORE_DECISIONS = frozenset({"accept", "repair", "regenerate", "ask_user", "fail"})
SCORECARD_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "scorecard_id",
        "source_run_id",
        "source_node_id",
        "source_artifact_id",
        "overall",
        "dimensions",
        "decision",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "scorecard_id": {"type": "string"},
        "source_run_id": {"type": "string"},
        "source_node_id": {"type": "string"},
        "source_artifact_id": {"type": "string"},
        "overall": {"type": "number", "minimum": 0, "maximum": 1},
        "dimensions": {
            "type": "array",
            "minItems": len(SCORE_DIMENSIONS),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "score", "reason", "repair_instruction"],
                "properties": {
                    "name": {"type": "string", "enum": list(SCORE_DIMENSIONS)},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string", "minLength": 1},
                    "repair_instruction": {},
                },
            },
        },
        "decision": {"type": "string", "enum": sorted(SCORE_DECISIONS)},
    },
}
MODEL_CRITIQUE_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overall", "dimensions", "decision"],
    "properties": {
        "overall": SCORECARD_SCHEMA["properties"]["overall"],
        "dimensions": SCORECARD_SCHEMA["properties"]["dimensions"],
        "decision": SCORECARD_SCHEMA["properties"]["decision"],
    },
}
PLACEHOLDER_MARKERS = ("todo", "tbd", "[insert", "<placeholder>")


@dataclass(frozen=True)
class ScoreDimension:
    name: str
    score: float
    reason: str
    repair_instruction: str | None

    def __post_init__(self) -> None:
        if self.name not in SCORE_DIMENSIONS:
            raise ScorecardFailure(kind="scorecard_unknown_dimension", message=f"unsupported score dimension {self.name!r}")
        if not 0 <= self.score <= 1:
            raise ScorecardFailure(kind="scorecard_dimension_score_invalid", message="dimension scores must be within [0, 1]")
        if not self.reason.strip():
            raise ScorecardFailure(kind="scorecard_missing_reason", message="score dimensions require a reason")
        if self.repair_instruction is not None and not self.repair_instruction.strip():
            raise ScorecardFailure(kind="scorecard_invalid_repair_instruction", message="repair instructions must be non-empty when present")

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "score": self.score,
            "reason": self.reason,
            "repair_instruction": self.repair_instruction,
        }


@dataclass(frozen=True)
class Scorecard:
    scorecard_id: ScorecardId
    source_run_id: RunId
    source_node_id: NodeId
    source_artifact_id: ArtifactId
    dimensions: tuple[ScoreDimension, ...]
    overall: float
    decision: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ScorecardFailure(kind="scorecard_schema_version_invalid", message="scorecards currently require schema version 1")
        if len(self.dimensions) != len(SCORE_DIMENSIONS) or {item.name for item in self.dimensions} != set(SCORE_DIMENSIONS):
            raise ScorecardFailure(kind="scorecard_dimension_set_invalid", message="scorecards require every standard score dimension exactly once")
        if not 0 <= self.overall <= 1:
            raise ScorecardFailure(kind="scorecard_overall_invalid", message="scorecard overall score must be within [0, 1]")
        if self.decision not in SCORE_DECISIONS:
            raise ScorecardFailure(kind="scorecard_decision_invalid", message=f"unsupported scorecard decision {self.decision!r}")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scorecard_id": self.scorecard_id.value,
            "source_run_id": self.source_run_id.value,
            "source_node_id": self.source_node_id.value,
            "source_artifact_id": self.source_artifact_id.value,
            "overall": self.overall,
            "dimensions": [item.to_payload() for item in self.dimensions],
            "decision": self.decision,
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())


@dataclass(frozen=True)
class ArtifactScoreInput:
    source_run_id: RunId
    source_node: WorkNode
    source_artifact_id: ArtifactId
    artifact: TypedArtifact | None
    validation: NodeValidationResult
    rendered_output: str
    evidence_reference_ids: tuple[str, ...]
    addressed_constraints: tuple[str, ...]
    consistency_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScorecardFailure(AxiaError):
    """A deterministic failure while forming or interpreting a scorecard."""


def score_artifact(
    scorecard_id: ScorecardId,
    constitution: TaskConstitution,
    score_input: ArtifactScoreInput,
) -> Scorecard:
    """Apply transparent deterministic checks and derive a threshold-bound decision."""

    if score_input.validation.node_id != score_input.source_node.node_id:
        raise ScorecardFailure(
            kind="scorecard_validation_node_mismatch",
            message="scorecard validation evidence must belong to the scored node",
        )
    serialized_artifact = _serialized_artifact(score_input.artifact)
    dimensions = (
        _dimension("relevance", _mission_is_referenced(serialized_artifact, constitution.mission), "Reference the task mission in the artifact."),
        _dimension("completeness", score_input.validation.accepted, "Return a schema-valid output with every required field."),
        _dimension("consistency", not score_input.consistency_issues, "Resolve the identified consistency issue."),
        _dimension("specificity", len(serialized_artifact) >= 48, "Add concrete detail rather than a short generic response."),
        _dimension(
            "evidence_use",
            bool(score_input.evidence_reference_ids) or not constitution.required_evidence,
            "Include at least one relevant evidence reference.",
        ),
        _dimension(
            "constraint_compliance",
            set(constitution.constraints).issubset(set(score_input.addressed_constraints)),
            "Address every task constraint explicitly.",
        ),
        _dimension("final_usability", _is_usable(score_input.rendered_output), "Replace placeholders and provide a usable final form."),
    )
    overall = _weighted_overall(dimensions, constitution)
    decision = _decision_for(dimensions, score_input.source_node.score_policy)
    return Scorecard(
        scorecard_id=scorecard_id,
        source_run_id=score_input.source_run_id,
        source_node_id=score_input.source_node.node_id,
        source_artifact_id=score_input.source_artifact_id,
        dimensions=dimensions,
        overall=overall,
        decision=decision,
    )


def scorecard_from_model_critique(
    scorecard_id: ScorecardId,
    constitution: TaskConstitution,
    source_run_id: RunId,
    source_node: WorkNode,
    source_artifact_id: ArtifactId,
    response_text: str,
) -> Scorecard:
    """Admit model critique only when its schema, aggregate, and decision meet controller policy."""

    parsed = parse_and_validate_json_object(response_text, MODEL_CRITIQUE_SCHEMA)
    if not parsed.accepted:
        issue = parsed.validation_errors[0]
        raise ScorecardFailure(kind="scorecard_model_schema_invalid", message=f"{issue.path} {issue.message}")
    assert parsed.payload is not None
    raw_dimensions = parsed.payload["dimensions"]
    assert isinstance(raw_dimensions, list)
    dimensions = tuple(_dimension_from_model(value) for value in raw_dimensions)
    supplied_overall = parsed.payload["overall"]
    supplied_decision = parsed.payload["decision"]
    assert isinstance(supplied_overall, (int, float)) and not isinstance(supplied_overall, bool)
    assert isinstance(supplied_decision, str)
    scorecard = Scorecard(
        scorecard_id=scorecard_id,
        source_run_id=source_run_id,
        source_node_id=source_node.node_id,
        source_artifact_id=source_artifact_id,
        dimensions=dimensions,
        overall=float(supplied_overall),
        decision=supplied_decision,
    )
    expected_overall = _weighted_overall(scorecard.dimensions, constitution)
    expected_decision = _decision_for(scorecard.dimensions, source_node.score_policy)
    if abs(scorecard.overall - expected_overall) > 0.000001:
        raise ScorecardFailure(
            kind="scorecard_model_overall_invalid",
            message="model scorecard overall must match the controller-weighted aggregate",
        )
    if scorecard.decision != expected_decision:
        raise ScorecardFailure(
            kind="scorecard_model_decision_invalid",
            message="model scorecard decision must match controller thresholds",
        )
    return scorecard


def _dimension_from_model(value: object) -> ScoreDimension:
    if not isinstance(value, Mapping):
        raise ScorecardFailure(kind="scorecard_model_dimension_invalid", message="model scorecard dimensions must be objects")
    repair_instruction = value.get("repair_instruction")
    if repair_instruction is not None and not isinstance(repair_instruction, str):
        raise ScorecardFailure(kind="scorecard_model_dimension_invalid", message="model repair instructions must be strings or null")
    name = value.get("name")
    score = value.get("score")
    reason = value.get("reason")
    if not isinstance(name, str) or not isinstance(score, (int, float)) or isinstance(score, bool) or not isinstance(reason, str):
        raise ScorecardFailure(kind="scorecard_model_dimension_invalid", message="model scorecard dimension fields have invalid types")
    return ScoreDimension(name=name, score=float(score), reason=reason, repair_instruction=repair_instruction)


def _dimension(name: str, passed: bool, repair_instruction: str) -> ScoreDimension:
    return ScoreDimension(
        name=name,
        score=1.0 if passed else 0.0,
        reason="deterministic check passed" if passed else "deterministic check failed",
        repair_instruction=None if passed else repair_instruction,
    )


def _serialized_artifact(artifact: TypedArtifact | None) -> str:
    return json.dumps(artifact.payload if artifact is not None else {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _mission_is_referenced(serialized_artifact: str, mission: str) -> bool:
    terms = tuple(term for term in re.findall(r"[a-z0-9]+", mission.lower()) if len(term) > 2)
    return bool(terms) and any(term in serialized_artifact.lower() for term in terms)


def _is_usable(rendered_output: str) -> bool:
    lowered = rendered_output.strip().lower()
    return bool(lowered) and not any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _weighted_overall(dimensions: tuple[ScoreDimension, ...], constitution: TaskConstitution) -> float:
    weights = {criterion.dimension: criterion.weight for criterion in constitution.quality_rubric}
    weighted_scores = [(dimension.score, weights.get(dimension.name, 1.0)) for dimension in dimensions]
    total_weight = sum(weight for _, weight in weighted_scores)
    return sum(score * weight for score, weight in weighted_scores) / total_weight


def _decision_for(dimensions: tuple[ScoreDimension, ...], policy: ScorePolicy) -> str:
    return policy.decision_for(min(dimension.score for dimension in dimensions))
