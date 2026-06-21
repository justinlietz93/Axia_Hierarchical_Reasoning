from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from axia.benchmark.report import BenchmarkReport
from axia.benchmark.scorecard import BENCHMARK_SCORE_DIMENSIONS


MVP_MEDIAN_SCORE_DELTA = 0.20
_TUNING_TARGETS = {
    "final_answer_usefulness": "prompts",
    "task_decomposition_quality": "graph",
    "schema_validity": "scoring_thresholds",
    "constraint_compliance": "prompts",
    "evidence_support": "graph",
    "repair_effectiveness": "repair_policy",
    "replayability": "scoring_thresholds",
}


@dataclass(frozen=True)
class BenchmarkImprovementResult:
    """Paired baseline-versus-standard evidence for the MVP reasoning-uplift claim."""

    baseline_median: float
    standard_median: float
    median_score_delta: float
    required_median_delta: float
    gate_passed: bool
    failure_categories: dict[str, tuple[str, ...]]
    tuning_targets: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "baseline_median": self.baseline_median,
            "standard_median": self.standard_median,
            "median_score_delta": self.median_score_delta,
            "required_median_delta": self.required_median_delta,
            "gate_passed": self.gate_passed,
            "failure_categories": {task_id: list(categories) for task_id, categories in self.failure_categories.items()},
            "tuning_targets": list(self.tuning_targets),
        }


def compare_mvp_improvement(
    report: BenchmarkReport,
    *,
    required_median_delta: float = MVP_MEDIAN_SCORE_DELTA,
) -> BenchmarkImprovementResult:
    """Compare paired standard and single-shot scores without treating missing evidence as uplift."""

    if not 0 < required_median_delta <= 1:
        raise ValueError("the MVP median score delta must be within (0, 1]")
    if report.scoring_configuration is None:
        raise ValueError("MVP comparison requires a recorded benchmark scoring configuration")
    scores = {(record.task.task_id, record.execution.mode): record.execution.benchmark_scorecard for record in report.records}
    baseline_scores = []
    standard_scores = []
    failures: dict[str, tuple[str, ...]] = {}
    tuning_targets: set[str] = set()
    for task in report.suite.tasks:
        baseline = scores[(task.task_id, "single_shot")]
        standard = scores[(task.task_id, "standard")]
        if baseline is None or standard is None:
            raise ValueError("MVP comparison requires scored single-shot and standard executions")
        baseline_scores.append(baseline.overall)
        standard_scores.append(standard.overall)
        categories = _failure_categories(baseline, standard)
        if categories:
            failures[task.task_id] = categories
            tuning_targets.update(_TUNING_TARGETS[category] for category in categories if category in _TUNING_TARGETS)
    baseline_median = median(baseline_scores)
    standard_median = median(standard_scores)
    median_delta = standard_median - baseline_median
    gate_passed = median_delta >= required_median_delta
    if not gate_passed:
        tuning_targets.add("scoring_thresholds")
    return BenchmarkImprovementResult(
        baseline_median=baseline_median,
        standard_median=standard_median,
        median_score_delta=median_delta,
        required_median_delta=required_median_delta,
        gate_passed=gate_passed,
        failure_categories=failures,
        tuning_targets=tuple(sorted(tuning_targets)),
    )


def _failure_categories(baseline, standard) -> tuple[str, ...]:
    categories = []
    if standard.overall <= baseline.overall:
        categories.append("final_answer_usefulness")
    baseline_dimensions = {dimension.name: dimension.score for dimension in baseline.dimensions}
    for dimension in BENCHMARK_SCORE_DIMENSIONS:
        standard_score = next(item.score for item in standard.dimensions if item.name == dimension)
        baseline_score = baseline_dimensions[dimension]
        if standard_score is None or (baseline_score is not None and standard_score <= baseline_score):
            categories.append(dimension)
    return tuple(dict.fromkeys(categories))
