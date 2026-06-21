from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Protocol

from axia.benchmark.evidence import BenchmarkControlEvidence
from axia.benchmark.report import BenchmarkRecord, BenchmarkReport
from axia.benchmark.runner import BenchmarkExecution
from axia.benchmark.scorecard import (
    BENCHMARK_SCORE_DIMENSIONS,
    BenchmarkDimensionScore,
    BenchmarkScoringConfiguration,
    BenchmarkScorecard,
)
from axia.benchmark.suite import BenchmarkTask


_PLACEHOLDER_MARKERS = ("todo", "tbd", "[insert", "<placeholder>")
_NON_TOPIC_TERMS = frozenset(
    {
        "about",
        "after",
        "against",
        "between",
        "create",
        "design",
        "from",
        "into",
        "local",
        "only",
        "output",
        "request",
        "should",
        "that",
        "this",
        "with",
    }
)


@dataclass(frozen=True)
class AnswerUsefulnessAssessment:
    """An evaluator's bounded judgment of the final user-facing output."""

    score: float
    reason: str

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("answer usefulness scores must be within [0, 1]")
        if not self.reason.strip():
            raise ValueError("answer usefulness assessments require a reason")


class AnswerUsefulnessEvaluator(Protocol):
    def assess(self, task: BenchmarkTask, output: str) -> AnswerUsefulnessAssessment:
        """Assess one final answer using the same evaluator for each compared mode."""


@dataclass(frozen=True)
class LexicalAnswerUsefulnessEvaluator:
    """A deterministic lower-bound evaluator, not a claim of semantic answer correctness."""

    minimum_distinct_terms: int = 24

    def __post_init__(self) -> None:
        if self.minimum_distinct_terms <= 0:
            raise ValueError("minimum distinct terms must be greater than zero")

    def assess(self, task: BenchmarkTask, output: str) -> AnswerUsefulnessAssessment:
        lowered = output.strip().lower()
        if not lowered or any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            return AnswerUsefulnessAssessment(0.0, "final output is empty or contains a placeholder marker")
        answer_terms = _terms(output)
        task_terms = _terms(" ".join((task.request, task.deliverable_type, task.output_format)))
        topic_target = min(3, len(task_terms))
        topic_coverage = min(1.0, len(answer_terms & task_terms) / topic_target) if topic_target else 0.0
        detail = min(1.0, len(answer_terms) / self.minimum_distinct_terms)
        score = (0.65 * topic_coverage) + (0.35 * detail)
        return AnswerUsefulnessAssessment(
            score=score,
            reason=(
                "deterministic lower-bound: "
                f"topic_coverage={topic_coverage:.2f}, detail={detail:.2f}"
            ),
        )


@dataclass(frozen=True)
class BenchmarkScorer:
    """Scores final answers and trace-backed reasoning controls under one fixed rubric."""

    answer_evaluator: AnswerUsefulnessEvaluator = field(default_factory=LexicalAnswerUsefulnessEvaluator)
    scoring_configuration: BenchmarkScoringConfiguration | None = None

    def __post_init__(self) -> None:
        if self.scoring_configuration is not None:
            return
        if not isinstance(self.answer_evaluator, LexicalAnswerUsefulnessEvaluator):
            raise ValueError("custom benchmark answer evaluators require an explicit scoring configuration")
        object.__setattr__(
            self,
            "scoring_configuration",
            BenchmarkScoringConfiguration(
                evaluator_id="lexical_lower_bound_v1",
                parameters={"minimum_distinct_terms": str(self.answer_evaluator.minimum_distinct_terms)},
            ),
        )

    def score_execution(self, task: BenchmarkTask, execution: BenchmarkExecution) -> BenchmarkExecution:
        dimensions = (
            _answer_dimension(task, execution, self.answer_evaluator),
            _decomposition_dimension(task, execution.control_evidence),
            _schema_dimension(execution.control_evidence),
            _constraint_dimension(task, execution.control_evidence),
            _evidence_dimension(execution.control_evidence),
            _repair_dimension(execution.control_evidence),
            _replay_dimension(execution.control_evidence),
        )
        scorecard = BenchmarkScorecard.from_dimensions(
            task_id=task.task_id,
            mode=execution.mode,
            source_run_id=execution.run_id,
            dimensions=dimensions,
        )
        return replace(execution, benchmark_scorecard=scorecard)


def score_benchmark_report(
    report: BenchmarkReport,
    scorer: BenchmarkScorer | None = None,
) -> BenchmarkReport:
    """Attach one comparison scorecard to each already-executed benchmark record."""

    selected_scorer = scorer or BenchmarkScorer()
    assert selected_scorer.scoring_configuration is not None
    return BenchmarkReport(
        suite=report.suite,
        records=tuple(
            BenchmarkRecord(task=record.task, execution=selected_scorer.score_execution(record.task, record.execution))
            for record in report.records
        ),
        scoring_configuration=selected_scorer.scoring_configuration,
        schema_version=report.schema_version,
    )


def _answer_dimension(
    task: BenchmarkTask,
    execution: BenchmarkExecution,
    evaluator: AnswerUsefulnessEvaluator,
) -> BenchmarkDimensionScore:
    assessment = evaluator.assess(task, execution.output)
    return BenchmarkDimensionScore("final_answer_usefulness", assessment.score, assessment.reason)


def _decomposition_dimension(
    task: BenchmarkTask,
    controls: BenchmarkControlEvidence | None,
) -> BenchmarkDimensionScore:
    if controls is None or not controls.decomposition_steps:
        return BenchmarkDimensionScore("task_decomposition_quality", 0.0, "no typed decomposition steps were recorded")
    covered = {
        constraint
        for step in controls.decomposition_steps
        for constraint in step.covered_constraints
        if constraint in task.constraints
    }
    coverage = _coverage(task.constraints, covered)
    structure = 1.0 if len(controls.decomposition_steps) >= 2 else 0.5
    return BenchmarkDimensionScore(
        "task_decomposition_quality",
        (0.75 * coverage) + (0.25 * structure),
        (
            "typed decomposition coverage="
            f"{coverage:.2f}; step_structure={structure:.2f}"
        ),
    )


def _schema_dimension(controls: BenchmarkControlEvidence | None) -> BenchmarkDimensionScore:
    if controls is None or controls.schema_valid is None:
        return BenchmarkDimensionScore("schema_validity", 0.0, "no schema validation result was recorded")
    if controls.schema_valid:
        return BenchmarkDimensionScore("schema_validity", 1.0, "recorded schema validation passed")
    return BenchmarkDimensionScore("schema_validity", 0.0, "recorded schema validation failed")


def _constraint_dimension(
    task: BenchmarkTask,
    controls: BenchmarkControlEvidence | None,
) -> BenchmarkDimensionScore:
    addressed = set(controls.addressed_constraints) if controls is not None else set()
    coverage = _coverage(task.constraints, addressed)
    return BenchmarkDimensionScore(
        "constraint_compliance",
        coverage,
        f"trace-backed addressed-constraint coverage={coverage:.2f}",
    )


def _evidence_dimension(controls: BenchmarkControlEvidence | None) -> BenchmarkDimensionScore:
    if controls is None or not controls.output_claim_ids:
        return BenchmarkDimensionScore("evidence_support", 0.0, "no output claim-to-evidence links were recorded")
    supported_claims = {support.claim_id for support in controls.evidence_support}
    score = len(supported_claims) / len(controls.output_claim_ids)
    return BenchmarkDimensionScore(
        "evidence_support",
        score,
        f"trace-backed evidence support covers {len(supported_claims)} of {len(controls.output_claim_ids)} output claims",
    )


def _repair_dimension(controls: BenchmarkControlEvidence | None) -> BenchmarkDimensionScore:
    if controls is None or not controls.repair_attempts:
        return BenchmarkDimensionScore(
            "repair_effectiveness",
            None,
            "no repair attempt was recorded; repair effectiveness is not assessed",
        )
    improvements = []
    for repair in controls.repair_attempts:
        if not repair.accepted or repair.before_score >= 1:
            improvements.append(0.0)
        else:
            improvements.append(max(0.0, repair.after_score - repair.before_score) / (1 - repair.before_score))
    score = sum(improvements) / len(improvements)
    return BenchmarkDimensionScore(
        "repair_effectiveness",
        score,
        f"normalized repair improvement across {len(improvements)} recorded attempts={score:.2f}",
    )


def _replay_dimension(controls: BenchmarkControlEvidence | None) -> BenchmarkDimensionScore:
    if controls is None or controls.replay is None:
        return BenchmarkDimensionScore("replayability", 0.0, "no replay verification was recorded")
    if controls.replay.replay_succeeded:
        return BenchmarkDimensionScore(
            "replayability",
            1.0,
            f"replay succeeded for manifest {controls.replay.manifest_hash}",
        )
    return BenchmarkDimensionScore(
        "replayability",
        0.0,
        f"replay failed for manifest {controls.replay.manifest_hash}",
    )


def _coverage(required: tuple[str, ...], observed: set[str]) -> float:
    if not required:
        return 1.0
    return len(set(required) & observed) / len(required)


def _terms(value: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", value.lower())
        if len(term) > 2 and term not in _NON_TOPIC_TERMS
    }


assert len(BENCHMARK_SCORE_DIMENSIONS) == 7
