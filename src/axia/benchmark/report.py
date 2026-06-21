from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.benchmark.runner import BENCHMARK_MODES, BenchmarkExecution
from axia.benchmark.suite import BenchmarkSuite, BenchmarkTask
from axia.shared.ids import stable_json_hash


BENCHMARK_REPORT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "suite", "records", "summary_metrics"],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "suite": {"type": "object"},
        "records": {"type": "array"},
        "summary_metrics": {"type": "object"},
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
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("benchmark reports currently require schema version 1")
        expected_keys = {(task.task_id, mode) for task in self.suite.tasks for mode in BENCHMARK_MODES}
        actual_keys = {(record.task.task_id, record.execution.mode) for record in self.records}
        if actual_keys != expected_keys or len(self.records) != len(expected_keys):
            raise ValueError("benchmark reports require exactly one record for every suite task and benchmark mode")

    def summary_metrics(self) -> dict[str, object]:
        summaries: dict[str, object] = {}
        for mode in BENCHMARK_MODES:
            executions = [record.execution for record in self.records if record.execution.mode == mode]
            summaries[mode] = {
                "run_count": len(executions),
                "scored_output_count": sum(execution.scorecard is not None for execution in executions),
                "average_output_characters": sum(len(execution.output) for execution in executions) / len(executions),
            }
        return summaries

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "suite": self.suite.to_payload(),
            "records": [record.to_payload() for record in self.records],
            "summary_metrics": self.summary_metrics(),
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())
