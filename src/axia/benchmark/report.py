from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.benchmark.runner import BENCHMARK_MODES, BenchmarkExecution
from axia.benchmark.scorecard import BENCHMARK_SCORE_DIMENSIONS, BenchmarkScoringConfiguration
from axia.benchmark.suite import BenchmarkSuite, BenchmarkTask
from axia.shared.ids import stable_json_hash


BENCHMARK_REPORT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "suite", "records", "summary_metrics", "scoring_configuration"],
    "properties": {
        "schema_version": {"type": "integer", "const": 2},
        "suite": {"type": "object"},
        "records": {"type": "array"},
        "summary_metrics": {"type": "object"},
        "scoring_configuration": {},
    },
}


@dataclass(frozen=True)
class BenchmarkRecord:
    """The complete stored comparison evidence for one task and one mode."""

    task: BenchmarkTask
    execution: BenchmarkExecution

    def __post_init__(self) -> None:
        if self.task.task_id != self.execution.task_id:
            raise ValueError("benchmark record task and execution IDs must match")

    def to_payload(self) -> dict[str, object]:
        return {"input": self.task.to_payload(), "execution": self.execution.to_payload()}


@dataclass(frozen=True)
class BenchmarkReport:
    """Versioned storage projection for benchmark inputs, outputs, scorecards, and summary metrics."""

    suite: BenchmarkSuite
    records: tuple[BenchmarkRecord, ...]
    scoring_configuration: BenchmarkScoringConfiguration | None = None
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError("benchmark reports currently require schema version 2")
        expected_keys = {(task.task_id, mode) for task in self.suite.tasks for mode in BENCHMARK_MODES}
        actual_keys = {(record.task.task_id, record.execution.mode) for record in self.records}
        if actual_keys != expected_keys or len(self.records) != len(expected_keys):
            raise ValueError("benchmark reports require exactly one record for every suite task and benchmark mode")

    def summary_metrics(self) -> dict[str, object]:
        summaries: dict[str, object] = {}
        for mode in BENCHMARK_MODES:
            executions = [record.execution for record in self.records if record.execution.mode == mode]
            benchmark_scorecards = [execution.benchmark_scorecard for execution in executions if execution.benchmark_scorecard is not None]
            dimension_scores = {
                dimension: [
                    score.score
                    for scorecard in benchmark_scorecards
                    for score in scorecard.dimensions
                    if score.name == dimension and score.score is not None
                ]
                for dimension in BENCHMARK_SCORE_DIMENSIONS
            }
            summaries[mode] = {
                "run_count": len(executions),
                "scored_output_count": sum(execution.scorecard is not None for execution in executions),
                "average_output_characters": sum(len(execution.output) for execution in executions) / len(executions),
                "benchmark_scorecard_count": len(benchmark_scorecards),
                "average_benchmark_score": (
                    sum(scorecard.overall for scorecard in benchmark_scorecards) / len(benchmark_scorecards)
                    if benchmark_scorecards
                    else None
                ),
                "benchmark_dimension_averages": {
                    dimension: (sum(scores) / len(scores) if scores else None)
                    for dimension, scores in dimension_scores.items()
                },
            }
        return summaries

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "suite": self.suite.to_payload(),
            "records": [record.to_payload() for record in self.records],
            "summary_metrics": self.summary_metrics(),
            "scoring_configuration": (
                self.scoring_configuration.to_payload() if self.scoring_configuration is not None else None
            ),
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())
