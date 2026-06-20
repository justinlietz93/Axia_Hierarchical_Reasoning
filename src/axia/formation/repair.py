from __future__ import annotations

from dataclasses import dataclass

from axia.formation.context_pack import ContextReference
from axia.formation.scorecard import ArtifactScoreInput, ScoreDimension, Scorecard
from axia.formation.task_constitution import TaskConstitution
from axia.formation.work_graph import ScorePolicy, WorkNode
from axia.shared.errors import AxiaError
from axia.shared.ids import ArtifactId, NodeId, RunId


REPAIR_CONTEXT_SCOPES = (
    "failed_artifact",
    "scorecard",
    "relevant_evidence",
    "repair_target",
)


@dataclass(frozen=True)
class RepairContext:
    """The complete, deliberately narrow evidence admitted for one repair attempt."""

    source_run_id: RunId
    source_node_id: NodeId
    source_artifact_id: ArtifactId
    failed_artifact_payload: dict[str, object] | None
    failed_rendered_output: str
    validation_errors: tuple[dict[str, str], ...]
    scorecard: Scorecard
    source_score_policy: ScorePolicy
    failed_dimensions: tuple[ScoreDimension, ...]
    relevant_evidence: tuple[ContextReference, ...]
    target_threshold: float

    def __post_init__(self) -> None:
        if (
            self.scorecard.source_run_id != self.source_run_id
            or self.scorecard.source_node_id != self.source_node_id
            or self.scorecard.source_artifact_id != self.source_artifact_id
        ):
            raise RepairFailure(
                kind="repair_context_lineage_mismatch",
                message="repair context must preserve the scorecard's run, node, and artifact lineage",
            )
        if not 0 < self.target_threshold <= 1:
            raise RepairFailure(
                kind="repair_context_target_invalid",
                message="repair target thresholds must be within (0, 1]",
            )
        if self.target_threshold != self.source_score_policy.accept_threshold:
            raise RepairFailure(
                kind="repair_context_target_mismatch",
                message="repair target threshold must match the source node acceptance threshold",
            )
        lowest_score = min(dimension.score for dimension in self.scorecard.dimensions)
        expected_decision = self.source_score_policy.decision_for(lowest_score)
        if self.scorecard.decision != expected_decision or expected_decision != "repair":
            raise RepairFailure(
                kind="repair_context_policy_mismatch",
                message="repair context requires a scorecard routed to repair by the source node policy",
            )
        if not self.failed_dimensions:
            raise RepairFailure(
                kind="repair_context_no_failed_dimensions",
                message="repair context requires at least one dimension below the target threshold",
            )
        if any(dimension.score >= self.target_threshold for dimension in self.failed_dimensions):
            raise RepairFailure(
                kind="repair_context_dimension_not_failed",
                message="repair context may include only dimensions below the target threshold",
            )
        expected_failed_dimensions = tuple(
            dimension for dimension in self.scorecard.dimensions if dimension.score < self.target_threshold
        )
        if self.failed_dimensions != expected_failed_dimensions:
            raise RepairFailure(
                kind="repair_context_dimension_set_mismatch",
                message="repair context must include every and only failed scorecard dimensions",
            )
        if any(reference.source_type != "evidence" for reference in self.relevant_evidence):
            raise RepairFailure(
                kind="repair_context_invalid_evidence",
                message="repair context admits only explicit evidence references as relevant evidence",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "source_run_id": self.source_run_id.value,
            "source_node_id": self.source_node_id.value,
            "source_artifact": {
                "artifact_id": self.source_artifact_id.value,
                "payload": self.failed_artifact_payload,
                "rendered_output": self.failed_rendered_output,
                "validation_errors": list(self.validation_errors),
            },
            "scorecard": self.scorecard.to_payload(),
            "failed_dimensions": [dimension.to_payload() for dimension in self.failed_dimensions],
            "relevant_evidence": [reference.to_payload() for reference in self.relevant_evidence],
            "target_threshold": self.target_threshold,
        }


@dataclass(frozen=True)
class RepairBudget:
    """Run-local accounting that prevents repair from exceeding declared execution limits."""

    run_id: RunId
    model_calls_used: int
    repair_attempts_by_node: tuple[tuple[NodeId, int], ...] = ()

    def __post_init__(self) -> None:
        if self.model_calls_used < 0:
            raise RepairFailure(
                kind="repair_budget_model_calls_invalid",
                message="used model calls must not be negative",
            )
        node_ids = [node_id for node_id, _ in self.repair_attempts_by_node]
        if len(set(node_ids)) != len(node_ids):
            raise RepairFailure(
                kind="repair_budget_duplicate_node",
                message="repair attempts must have one count per node",
            )
        if any(attempts <= 0 for _, attempts in self.repair_attempts_by_node):
            raise RepairFailure(
                kind="repair_budget_attempts_invalid",
                message="recorded repair attempts must be positive",
            )
        if sum(attempts for _, attempts in self.repair_attempts_by_node) > self.model_calls_used:
            raise RepairFailure(
                kind="repair_budget_calls_inconsistent",
                message="repair attempts cannot exceed the total recorded model calls",
            )
        if tuple(sorted(self.repair_attempts_by_node, key=lambda item: item[0].value)) != self.repair_attempts_by_node:
            raise RepairFailure(
                kind="repair_budget_order_invalid",
                message="repair attempt counts must be ordered by node ID",
            )

    def attempts_for(self, node_id: NodeId) -> int:
        return next((attempts for candidate, attempts in self.repair_attempts_by_node if candidate == node_id), 0)

    def with_admitted_attempt(self, node_id: NodeId) -> RepairBudget:
        counts = {candidate: attempts for candidate, attempts in self.repair_attempts_by_node}
        counts[node_id] = counts.get(node_id, 0) + 1
        return RepairBudget(
            run_id=self.run_id,
            model_calls_used=self.model_calls_used + 1,
            repair_attempts_by_node=tuple(sorted(counts.items(), key=lambda item: item[0].value)),
        )


@dataclass(frozen=True)
class RepairAdmission:
    """An approved repair call and the run-local budget state after reserving it."""

    repair_context: RepairContext
    repair_node_id: NodeId
    attempt_number: int
    next_budget: RepairBudget


@dataclass(frozen=True)
class RepairFailure(AxiaError):
    """A deterministic refusal to form or admit a bounded repair attempt."""


def form_repair_context(
    score_input: ArtifactScoreInput,
    scorecard: Scorecard,
    relevant_evidence: tuple[ContextReference, ...],
) -> RepairContext:
    """Form repair input only for the dimensions the node policy actually permits repairing."""

    source_node = score_input.source_node
    if (
        scorecard.source_run_id != score_input.source_run_id
        or scorecard.source_node_id != source_node.node_id
        or scorecard.source_artifact_id != score_input.source_artifact_id
    ):
        raise RepairFailure(
            kind="repair_scorecard_lineage_mismatch",
            message="repair requires a scorecard for the exact failed artifact and source node",
        )
    if score_input.validation.node_id != source_node.node_id:
        raise RepairFailure(
            kind="repair_validation_node_mismatch",
            message="repair validation evidence must belong to the failed artifact's source node",
        )

    lowest_score = min(dimension.score for dimension in scorecard.dimensions)
    expected_decision = source_node.score_policy.decision_for(lowest_score)
    if scorecard.decision != expected_decision:
        raise RepairFailure(
            kind="repair_scorecard_decision_mismatch",
            message="repair requires the scorecard decision derived from the source node policy",
        )
    if expected_decision != "repair":
        raise RepairFailure(
            kind="repair_not_admitted",
            message=f"score policy selected {expected_decision!r}, not bounded repair",
        )

    target_threshold = source_node.score_policy.accept_threshold
    failed_dimensions = tuple(dimension for dimension in scorecard.dimensions if dimension.score < target_threshold)
    artifact_payload = dict(score_input.artifact.payload) if score_input.artifact is not None else None
    validation_errors = tuple(
        {
            "path": issue.path,
            "rule": issue.rule,
            "message": issue.message,
        }
        for issue in score_input.validation.validation_errors
    )
    return RepairContext(
        source_run_id=score_input.source_run_id,
        source_node_id=source_node.node_id,
        source_artifact_id=score_input.source_artifact_id,
        failed_artifact_payload=artifact_payload,
        failed_rendered_output=score_input.rendered_output,
        validation_errors=validation_errors,
        scorecard=scorecard,
        source_score_policy=source_node.score_policy,
        failed_dimensions=failed_dimensions,
        relevant_evidence=relevant_evidence,
        target_threshold=target_threshold,
    )


def admit_repair_attempt(
    repair_node: WorkNode,
    repair_context: RepairContext,
    constitution: TaskConstitution,
    budget: RepairBudget,
) -> RepairAdmission:
    """Reserve one repair model call only while node and run budgets still permit it."""

    if repair_node.kind != "repair":
        raise RepairFailure(
            kind="repair_node_kind_invalid",
            message="only a repair work node may receive a repair admission",
        )
    if budget.run_id != repair_context.source_run_id:
        raise RepairFailure(
            kind="repair_budget_run_mismatch",
            message="repair budget and repair context must belong to the same run",
        )
    if budget.model_calls_used >= constitution.limits.max_model_calls:
        raise RepairFailure(
            kind="repair_model_call_limit_exhausted",
            message="repair would exceed the constitution's total model-call budget",
        )

    effective_retry_limit = min(repair_node.retry_limit, constitution.limits.max_retries_per_node)
    completed_attempts = budget.attempts_for(repair_node.node_id)
    if completed_attempts >= effective_retry_limit:
        raise RepairFailure(
            kind="repair_retry_limit_exhausted",
            message="repair would exceed the node or constitution retry limit",
        )

    next_budget = budget.with_admitted_attempt(repair_node.node_id)
    return RepairAdmission(
        repair_context=repair_context,
        repair_node_id=repair_node.node_id,
        attempt_number=next_budget.attempts_for(repair_node.node_id),
        next_budget=next_budget,
    )
