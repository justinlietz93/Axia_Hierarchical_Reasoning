from __future__ import annotations

import unittest

from axia.benchmark import (
    AnswerUsefulnessAssessment,
    BASELINE_BENCHMARK_SUITE,
    BENCHMARK_SCORE_DIMENSIONS,
    BenchmarkControlEvidence,
    BenchmarkDecompositionStep,
    BenchmarkEvidenceSupport,
    BenchmarkExecution,
    BenchmarkRecord,
    BenchmarkRepairAttempt,
    BenchmarkReplayEvidence,
    BenchmarkReport,
    BenchmarkScorer,
    BenchmarkScoringConfiguration,
    BenchmarkSuite,
    BenchmarkTask,
    LexicalAnswerUsefulnessEvaluator,
    score_benchmark_report,
)
from axia.shared.ids import RunId


class FixedAnswerUsefulnessEvaluator:
    def assess(self, task: BenchmarkTask, output: str) -> AnswerUsefulnessAssessment:
        return AnswerUsefulnessAssessment(0.8, "fixed evaluator applied equally to every compared mode")


def _task() -> BenchmarkTask:
    return BenchmarkTask(
        task_id="scored_reasoning",
        request="Recommend a bounded reasoning design with inspectable artifacts.",
        deliverable_type="technical recommendation",
        output_format="recommendation with caveats",
        constraints=("typed artifacts", "replayable"),
    )


def _controls(*, include_repair: bool = True) -> BenchmarkControlEvidence:
    return BenchmarkControlEvidence(
        decomposition_steps=(
            BenchmarkDecompositionStep("node_plan", "form the typed work plan", ("typed artifacts",)),
            BenchmarkDecompositionStep("node_verify", "verify and preserve replay evidence", ("replayable",)),
        ),
        schema_valid=True,
        addressed_constraints=("typed artifacts", "replayable"),
        output_claim_ids=("claim_recommendation", "claim_caveat"),
        evidence_support=(
            BenchmarkEvidenceSupport("claim_recommendation", "artifact_plan"),
            BenchmarkEvidenceSupport("claim_caveat", "artifact_verify"),
        ),
        repair_attempts=(BenchmarkRepairAttempt(1, before_score=0.4, after_score=0.7, accepted=True),)
        if include_repair
        else (),
        replay=BenchmarkReplayEvidence("manifest_hash", replay_succeeded=True),
    )


def _execution(mode: str, *, controls: BenchmarkControlEvidence | None = None) -> BenchmarkExecution:
    return BenchmarkExecution(
        task_id="scored_reasoning",
        mode=mode,
        run_id=RunId.from_value(f"run_benchmark_{mode}_scored_reasoning"),
        output="Use typed artifacts, validate each result, and retain the manifest needed to replay decisions.",
        scorecard={"decision": "accept", "overall": 0.9},
        metadata={"profile": "fake-tiny"},
        control_evidence=controls,
    )


def _scorer() -> BenchmarkScorer:
    return BenchmarkScorer(
        FixedAnswerUsefulnessEvaluator(),
        BenchmarkScoringConfiguration("fixed_answer_usefulness_v1", {"score": "0.8"}),
    )


class BenchmarkScoringTests(unittest.TestCase):
    def test_scores_final_answer_and_each_trace_backed_reasoning_control(self) -> None:
        scored = _scorer().score_execution(
            _task(),
            _execution("standard", controls=_controls()),
        )
        assert scored.benchmark_scorecard is not None
        dimensions = {dimension.name: dimension.score for dimension in scored.benchmark_scorecard.dimensions}

        self.assertEqual(tuple(dimensions), BENCHMARK_SCORE_DIMENSIONS)
        self.assertEqual(dimensions["final_answer_usefulness"], 0.8)
        self.assertEqual(dimensions["task_decomposition_quality"], 1.0)
        self.assertEqual(dimensions["schema_validity"], 1.0)
        self.assertEqual(dimensions["constraint_compliance"], 1.0)
        self.assertEqual(dimensions["evidence_support"], 1.0)
        self.assertAlmostEqual(dimensions["repair_effectiveness"], 0.5)
        self.assertEqual(dimensions["replayability"], 1.0)
        self.assertAlmostEqual(scored.benchmark_scorecard.overall, 0.9)
        self.assertEqual(scored.benchmark_scorecard.source_run_id, scored.run_id)

    def test_missing_controls_fail_and_unexercised_repair_is_not_counted_as_success(self) -> None:
        scored = _scorer().score_execution(
            _task(),
            _execution("single_shot"),
        )
        assert scored.benchmark_scorecard is not None
        dimensions = {dimension.name: dimension for dimension in scored.benchmark_scorecard.dimensions}

        self.assertEqual(dimensions["task_decomposition_quality"].score, 0.0)
        self.assertEqual(dimensions["schema_validity"].score, 0.0)
        self.assertEqual(dimensions["constraint_compliance"].score, 0.0)
        self.assertEqual(dimensions["evidence_support"].score, 0.0)
        self.assertEqual(dimensions["replayability"].score, 0.0)
        self.assertIsNone(dimensions["repair_effectiveness"].score)
        self.assertIn("not assessed", dimensions["repair_effectiveness"].reason)

    def test_report_persists_comparison_scorecards_and_mode_summaries(self) -> None:
        suite = BenchmarkSuite("scoring_v1", (_task(),))
        report = BenchmarkReport(
            suite=suite,
            records=(
                BenchmarkRecord(_task(), _execution("single_shot")),
                BenchmarkRecord(_task(), _execution("quick", controls=_controls(include_repair=False))),
                BenchmarkRecord(_task(), _execution("standard", controls=_controls())),
            ),
        )

        scored_report = score_benchmark_report(report, _scorer())
        payload = scored_report.to_payload()
        standard_summary = payload["summary_metrics"]["standard"]

        self.assertTrue(all(record.execution.benchmark_scorecard is not None for record in scored_report.records))
        self.assertEqual(standard_summary["benchmark_scorecard_count"], 1)
        self.assertAlmostEqual(standard_summary["average_benchmark_score"], 0.9)
        self.assertEqual(standard_summary["benchmark_dimension_averages"]["replayability"], 1.0)
        self.assertEqual(payload["records"][2]["execution"]["scorecard"]["decision"], "accept")
        self.assertEqual(payload["records"][2]["execution"]["benchmark_scorecard"]["task_id"], "scored_reasoning")
        self.assertEqual(payload["scoring_configuration"]["evaluator_id"], "fixed_answer_usefulness_v1")

    def test_rejects_evidence_that_does_not_link_to_a_declared_output_claim(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkControlEvidence(
                output_claim_ids=("claim_recommendation",),
                evidence_support=(BenchmarkEvidenceSupport("claim_unknown", "artifact_unknown"),),
            )

    def test_lexical_lower_bound_is_clamped_for_term_dense_answers(self) -> None:
        assessment = LexicalAnswerUsefulnessEvaluator().assess(
            _task(),
            " ".join(("bounded reasoning inspectable artifacts recommendation caveats " * 20).split()),
        )

        self.assertGreaterEqual(assessment.score, 0.0)
        self.assertLessEqual(assessment.score, 1.0)

    def test_baseline_suite_stays_available_for_scored_comparisons(self) -> None:
        self.assertGreaterEqual(len(BASELINE_BENCHMARK_SUITE.tasks), 20)


if __name__ == "__main__":
    unittest.main()
