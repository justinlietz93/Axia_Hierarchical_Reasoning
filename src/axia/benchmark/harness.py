from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.benchmark.report import BenchmarkRecord, BenchmarkReport
from axia.benchmark.runner import BENCHMARK_MODES, BenchmarkRunner
from axia.benchmark.scoring import BenchmarkScorer, score_benchmark_report
from axia.benchmark.suite import BenchmarkSuite
from axia.shared.errors import AxiaError


@dataclass(frozen=True)
class BenchmarkFailure(AxiaError):
    """A deterministic failure while forming a complete three-mode benchmark report."""


def run_benchmark_suite(
    suite: BenchmarkSuite,
    runners: Mapping[str, BenchmarkRunner],
    *,
    scorer: BenchmarkScorer | None = None,
) -> BenchmarkReport:
    """Run and score every fixed task once per declared mode under one comparison rubric."""

    if set(runners) != set(BENCHMARK_MODES):
        raise BenchmarkFailure(
            kind="benchmark_runner_set_invalid",
            message="benchmark harness requires exactly single_shot, quick, and standard runners",
        )
    records: list[BenchmarkRecord] = []
    for task in suite.tasks:
        for mode in BENCHMARK_MODES:
            runner = runners[mode]
            if runner.mode != mode:
                raise BenchmarkFailure(
                    kind="benchmark_runner_mode_mismatch",
                    message="benchmark runner mapping keys must match each runner's declared mode",
                )
            execution = runner.execute(task)
            if execution.mode != mode or execution.task_id != task.task_id:
                raise BenchmarkFailure(
                    kind="benchmark_execution_mismatch",
                    message="benchmark execution must preserve its requested task and mode",
                )
            records.append(BenchmarkRecord(task=task, execution=execution))
    return score_benchmark_report(BenchmarkReport(suite=suite, records=tuple(records)), scorer)
