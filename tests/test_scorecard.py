from __future__ import annotations

import json
import unittest

from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.ports.run_store import RunManifestRecord
from axia.formation import (
    ArtifactScoreInput,
    NodeValidationResult,
    ScorePolicy,
    ScorecardFailure,
    TypedArtifact,
    WorkNode,
    build_task_constitution,
    score_artifact,
    scorecard_from_model_critique,
    SCORECARD_SCHEMA,
)
from axia.formation.canonical_request import CanonicalRequest
from axia.operation import record_scorecard
from axia.shared.ids import ArtifactId, NodeId, RunId, ScorecardId


def _constitution():
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
        )
    )


def _node() -> WorkNode:
    return WorkNode(
        node_id=NodeId.from_value("node_verify"),
        kind="verify",
        depends_on=(),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        context_scope=("constitution",),
        allowed_operations=(),
        retry_limit=1,
        score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65),
        failure_behavior="fail_run",
    )


def _score_input(node: WorkNode, *, output: str, evidence: tuple[str, ...] = ("evidence_1",), constraints: tuple[str, ...] = ("local-first",)) -> ArtifactScoreInput:
    artifact = TypedArtifact.from_payload({"answer": output})
    return ArtifactScoreInput(
        source_run_id=RunId.from_value("run_score"),
        source_node=node,
        source_artifact_id=ArtifactId.from_value("artifact_answer"),
        artifact=artifact,
        validation=NodeValidationResult(node_id=node.node_id, artifact=artifact, validation_errors=()),
        rendered_output=output,
        evidence_reference_ids=evidence,
        addressed_constraints=constraints,
    )


class ScorecardTests(unittest.TestCase):
    def test_scores_every_required_dimension_and_records_lineage(self) -> None:
        node = _node()
        output = "Compare database options for a local-first system: SQLite is the practical default for this project."
        scorecard = score_artifact(
            ScorecardId.from_value("scorecard_verified_answer"),
            _constitution(),
            _score_input(node, output=output),
        )

        self.assertEqual(scorecard.decision, "accept")
        self.assertEqual(scorecard.overall, 1.0)
        self.assertEqual([dimension.name for dimension in scorecard.dimensions], [
            "relevance", "completeness", "consistency", "specificity", "evidence_use", "constraint_compliance", "final_usability",
        ])
        store = SQLiteRunStore(":memory:")
        store.create_run(RunManifestRecord(
            run_id=scorecard.source_run_id, created_at="2026-06-20T00:00:00Z", status="running", mode="standard", request_hash="request-hash", payload={"schema_version": 1},
        ))

        recorded = record_scorecard(scorecard, store)

        self.assertEqual(recorded.kind, "scorecard")
        self.assertEqual(recorded.payload["source_node_id"], "node_verify")
        self.assertEqual(recorded.payload["source_artifact_id"], "artifact_answer")

    def test_failed_deterministic_checks_require_clarification(self) -> None:
        scorecard = score_artifact(
            ScorecardId.from_value("scorecard_failed_answer"),
            _constitution(),
            _score_input(_node(), output="TBD", evidence=(), constraints=()),
        )

        failed_dimensions = [dimension for dimension in scorecard.dimensions if dimension.score == 0]
        self.assertEqual(scorecard.decision, "ask_user")
        self.assertTrue(all(dimension.repair_instruction for dimension in failed_dimensions))

    def test_model_critique_cannot_override_controller_aggregate_or_thresholds(self) -> None:
        payload = {
            "overall": 1.0,
            "decision": "accept",
            "dimensions": [
                {"name": name, "score": 1.0, "reason": "checked", "repair_instruction": None}
                for name in (
                    "relevance", "completeness", "consistency", "specificity", "evidence_use", "constraint_compliance", "final_usability",
                )
            ],
        }
        scorecard = scorecard_from_model_critique(
            ScorecardId.from_value("scorecard_model_critique"),
            _constitution(),
            RunId.from_value("run_score"),
            _node(),
            ArtifactId.from_value("artifact_answer"),
            json.dumps(payload),
        )

        payload["dimensions"][0]["score"] = 0.0
        with self.assertRaises(ScorecardFailure) as failure:
            scorecard_from_model_critique(
                ScorecardId.from_value("scorecard_invalid_model_critique"),
                _constitution(),
                RunId.from_value("run_score"),
                _node(),
                ArtifactId.from_value("artifact_answer"),
                json.dumps(payload),
            )

        self.assertEqual(scorecard.decision, "accept")
        self.assertIn("source_artifact_id", SCORECARD_SCHEMA["required"])
        self.assertEqual(failure.exception.kind, "scorecard_model_overall_invalid")
