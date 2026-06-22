from __future__ import annotations

import unittest

from axia.formation import (
    ArtifactScoreInput,
    ConstitutionLimits,
    ContextReference,
    MicroAgentContract,
    MicroAgentEvaluation,
    NodeValidationResult,
    RepairBudget,
    RepairFailure,
    ScoreDimension,
    ScorePolicy,
    Scorecard,
    TypedArtifact,
    WorkNode,
    admit_repair_attempt,
    build_task_constitution,
    form_repair_context,
)
from axia.formation.canonical_request import CanonicalRequest
from axia.operation import compile_micro_agent_request, pack_repair_context
from axia.shared.ids import ArtifactId, NodeId, RunId, ScorecardId


def _constitution(*, max_model_calls: int = 16, max_retries_per_node: int = 2):
    return build_task_constitution(
        CanonicalRequest(
            source_request_hash="request-hash",
            intent="compare database options",
            deliverable_type="technical recommendation",
            constraints=("local-first",),
            unknowns=(),
            risk_flags=(),
            output_format="concise recommendation",
            expected_depth="standard",
            needed_context=(),
        ),
        limits=ConstitutionLimits(
            max_depth=4,
            max_model_calls=max_model_calls,
            max_retries_per_node=max_retries_per_node,
            max_seconds=300,
        ),
    )


def _source_node() -> WorkNode:
    return WorkNode(
        node_id=NodeId.from_value("node_draft"),
        kind="draft",
        depends_on=(),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        context_scope=("plan",),
        allowed_operations=(),
        retry_limit=0,
        score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65, regenerate_threshold=0.45),
        failure_behavior="fail_run",
    )


def _repair_node(*, retry_limit: int = 2, context_scope: tuple[str, ...] = ("failed_artifact", "scorecard", "relevant_evidence", "repair_target")) -> WorkNode:
    return WorkNode(
        node_id=NodeId.from_value("node_repair"),
        kind="repair",
        depends_on=(NodeId.from_value("node_draft"),),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        context_scope=context_scope,
        allowed_operations=(),
        retry_limit=retry_limit,
        score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65, regenerate_threshold=0.45),
        failure_behavior="retry",
    )


def _score_input(source_node: WorkNode) -> ArtifactScoreInput:
    artifact = TypedArtifact.from_payload(
        {"answer": "SQLite keeps this local-first database recommendation practical and inspectable."}
    )
    return ArtifactScoreInput(
        source_run_id=RunId.from_value("run_repair"),
        source_node=source_node,
        source_artifact_id=ArtifactId.from_value("artifact_draft"),
        artifact=artifact,
        validation=NodeValidationResult(node_id=source_node.node_id, artifact=artifact, validation_errors=()),
        rendered_output=artifact.payload["answer"],
        evidence_reference_ids=("evidence_sqlite",),
        addressed_constraints=("local-first",),
    )


def _scorecard(source_node: WorkNode, *, failed_score: float) -> Scorecard:
    dimensions = tuple(
        ScoreDimension(
            name=name,
            score=failed_score if name == "specificity" else 1.0,
            reason="needs more concrete detail" if name == "specificity" else "checked",
            repair_instruction="Add concrete database tradeoffs." if name == "specificity" and failed_score < 0.82 else None,
        )
        for name in (
            "relevance",
            "completeness",
            "consistency",
            "specificity",
            "evidence_use",
            "constraint_compliance",
            "final_usability",
        )
    )
    return Scorecard(
        scorecard_id=ScorecardId.from_value("scorecard_draft"),
        source_run_id=RunId.from_value("run_repair"),
        source_node_id=source_node.node_id,
        source_artifact_id=ArtifactId.from_value("artifact_draft"),
        dimensions=dimensions,
        overall=sum(dimension.score for dimension in dimensions) / len(dimensions),
        decision=source_node.score_policy.decision_for(failed_score),
    )


def _evidence() -> tuple[ContextReference, ...]:
    return (
        ContextReference.from_content(
            scope="retrieved_evidence",
            source_type="evidence",
            reference_id="evidence_sqlite",
            content="SQLite is an embedded database appropriate for local-first applications.",
        ),
    )


class _AcceptingEvaluator:
    def evaluate(self, artifact: TypedArtifact) -> MicroAgentEvaluation:
        return MicroAgentEvaluation(accepted=True, reasons=())


class RepairTests(unittest.TestCase):
    def test_score_policy_has_explicit_repair_regenerate_and_clarification_bands(self) -> None:
        policy = ScorePolicy(accept_threshold=0.82, repair_threshold=0.65, regenerate_threshold=0.45)

        self.assertEqual(policy.decision_for(0.82), "accept")
        self.assertEqual(policy.decision_for(0.65), "repair")
        self.assertEqual(policy.decision_for(0.45), "regenerate")
        self.assertEqual(policy.decision_for(0.44), "ask_user")

    def test_repair_context_limits_model_input_to_failed_dimension_and_relevant_evidence(self) -> None:
        source_node = _source_node()
        context = form_repair_context(_score_input(source_node), _scorecard(source_node, failed_score=0.7), _evidence())

        repair_node = _repair_node()
        instruction = "Repair only the listed scorecard dimensions."
        pack = pack_repair_context(
            repair_node,
            context,
            _constitution(),
            node_instruction=instruction,
        )
        request = compile_micro_agent_request(
            MicroAgentContract(
                node=repair_node,
                role_prompt=instruction,
                output_schema=repair_node.output_schema,
                evaluator=_AcceptingEvaluator(),
            ),
            pack,
        )

        self.assertEqual([dimension.name for dimension in context.failed_dimensions], ["specificity"])
        self.assertEqual(context.target_threshold, 0.82)
        self.assertEqual(set(pack.prompt_inputs()), {"failed_artifact", "scorecard", "relevant_evidence", "repair_target"})
        self.assertFalse(next(reference for reference in pack.references if reference.scope == "failed_artifact").accepted)
        self.assertEqual(pack.prompt_inputs()["repair_target"]["failed_dimensions"][0]["name"], "specificity")
        self.assertIn('"failed_dimensions"', request.messages[0].content)
        self.assertIn('"target_threshold":0.82', request.messages[0].content)

    def test_nonrepair_scorecard_cannot_enter_a_repair_loop(self) -> None:
        source_node = _source_node()

        with self.assertRaises(RepairFailure) as failure:
            form_repair_context(_score_input(source_node), _scorecard(source_node, failed_score=0.5), _evidence())

        self.assertEqual(failure.exception.kind, "repair_not_admitted")

    def test_repair_admission_refuses_retry_and_total_call_limit_overruns(self) -> None:
        source_node = _source_node()
        context = form_repair_context(_score_input(source_node), _scorecard(source_node, failed_score=0.7), _evidence())
        constitution = _constitution(max_model_calls=3, max_retries_per_node=2)
        first = admit_repair_attempt(
            _repair_node(retry_limit=1),
            context,
            constitution,
            RepairBudget(run_id=context.source_run_id, model_calls_used=1),
        )

        with self.assertRaises(RepairFailure) as retry_failure:
            admit_repair_attempt(_repair_node(retry_limit=1), context, constitution, first.next_budget)
        with self.assertRaises(RepairFailure) as call_failure:
            admit_repair_attempt(
                _repair_node(retry_limit=2),
                context,
                _constitution(max_model_calls=2, max_retries_per_node=2),
                RepairBudget(run_id=context.source_run_id, model_calls_used=2),
            )
        constitution_limited = _constitution(max_model_calls=16, max_retries_per_node=1)
        constitution_first = admit_repair_attempt(
            _repair_node(retry_limit=3),
            context,
            constitution_limited,
            RepairBudget(run_id=context.source_run_id, model_calls_used=0),
        )
        with self.assertRaises(RepairFailure) as constitution_retry_failure:
            admit_repair_attempt(
                _repair_node(retry_limit=3),
                context,
                constitution_limited,
                constitution_first.next_budget,
            )

        self.assertEqual(first.attempt_number, 1)
        self.assertEqual(first.next_budget.model_calls_used, 2)
        self.assertEqual(retry_failure.exception.kind, "repair_retry_limit_exhausted")
        self.assertEqual(call_failure.exception.kind, "repair_model_call_limit_exhausted")
        self.assertEqual(constitution_retry_failure.exception.kind, "repair_retry_limit_exhausted")

    def test_repair_context_rejects_broad_or_missing_repair_scopes(self) -> None:
        source_node = _source_node()
        context = form_repair_context(_score_input(source_node), _scorecard(source_node, failed_score=0.7), _evidence())

        with self.assertRaises(RepairFailure) as failure:
            pack_repair_context(
                _repair_node(context_scope=("failed_artifact", "scorecard", "relevant_evidence", "repair_target", "full_run")),
                context,
                _constitution(),
                node_instruction="Repair only the listed scorecard dimensions.",
            )

        self.assertEqual(failure.exception.kind, "repair_context_scope_invalid")


if __name__ == "__main__":
    unittest.main()
