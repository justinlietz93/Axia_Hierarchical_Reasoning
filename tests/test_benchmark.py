from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from axia.benchmark import (
    BASELINE_BENCHMARK_SUITE,
    AxiaModeBenchmarkRunner,
    BenchmarkExecution,
    BenchmarkFailure,
    SingleShotBenchmarkRunner,
    run_benchmark_suite,
)
from axia.boundary.ports.model_provider import ModelRequest, ModelResponse
from axia.boundary.adapters.json_benchmark_report_store import JsonBenchmarkReportStore
from axia.shared.ids import RunId


class StaticProvider:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(text="single-shot response", metadata={"provider": "fake"})


class DeterministicAxiaExecutor:
    def execute(self, task, mode: str) -> BenchmarkExecution:
        return BenchmarkExecution(
            task_id=task.task_id,
            mode=mode,
            run_id=RunId.from_value(f"run_benchmark_{mode}_{task.task_id}"),
            output=f"{mode} output for {task.task_id}",
            scorecard={"decision": "accept", "overall": 1.0},
            metadata={"executor": "deterministic"},
        )


class BenchmarkTests(unittest.TestCase):
    def test_fixed_baseline_suite_covers_twenty_tasks(self) -> None:
        suite = BASELINE_BENCHMARK_SUITE

        self.assertEqual(suite.suite_id, "baseline_v1")
        self.assertGreaterEqual(len(suite.tasks), 20)
        self.assertEqual(len({task.task_id for task in suite.tasks}), len(suite.tasks))

    def test_runs_and_stores_every_task_in_all_three_modes(self) -> None:
        provider = StaticProvider()
        executor = DeterministicAxiaExecutor()

        report = run_benchmark_suite(
            BASELINE_BENCHMARK_SUITE,
            {
                "single_shot": SingleShotBenchmarkRunner(provider=provider, profile_name="tiny-default"),
                "quick": AxiaModeBenchmarkRunner(mode="quick", executor=executor),
                "standard": AxiaModeBenchmarkRunner(mode="standard", executor=executor),
            },
        )
        payload = report.to_payload()

        self.assertEqual(len(provider.requests), len(BASELINE_BENCHMARK_SUITE.tasks))
        self.assertEqual(len(report.records), len(BASELINE_BENCHMARK_SUITE.tasks) * 3)
        self.assertEqual(payload["summary_metrics"]["single_shot"]["run_count"], len(BASELINE_BENCHMARK_SUITE.tasks))
        self.assertEqual(payload["summary_metrics"]["quick"]["scored_output_count"], len(BASELINE_BENCHMARK_SUITE.tasks))
        self.assertEqual(payload["summary_metrics"]["standard"]["benchmark_scorecard_count"], len(BASELINE_BENCHMARK_SUITE.tasks))
        self.assertEqual(payload["records"][0]["input"]["task_id"], "database_choice")
        self.assertIn("run_id", payload["records"][0]["execution"])
        self.assertIsNotNone(payload["records"][0]["execution"]["benchmark_scorecard"])

        with TemporaryDirectory() as temporary_directory:
            destination = JsonBenchmarkReportStore(temporary_directory).write(report)
            stored_payload = json.loads(Path(destination).read_text(encoding="utf-8"))

        self.assertEqual(stored_payload, payload)

    def test_rejects_incomplete_or_mislabeled_runner_sets(self) -> None:
        provider = StaticProvider()
        single_shot = SingleShotBenchmarkRunner(provider=provider, profile_name="tiny-default")

        with self.assertRaises(BenchmarkFailure) as incomplete_failure:
            run_benchmark_suite(BASELINE_BENCHMARK_SUITE, {"single_shot": single_shot})

        with self.assertRaises(BenchmarkFailure) as mismatch_failure:
            run_benchmark_suite(
                BASELINE_BENCHMARK_SUITE,
                {
                    "single_shot": single_shot,
                    "quick": AxiaModeBenchmarkRunner(mode="quick", executor=DeterministicAxiaExecutor()),
                    "standard": AxiaModeBenchmarkRunner(mode="quick", executor=DeterministicAxiaExecutor()),
                },
            )

        self.assertEqual(incomplete_failure.exception.kind, "benchmark_runner_set_invalid")
        self.assertEqual(mismatch_failure.exception.kind, "benchmark_runner_mode_mismatch")


if __name__ == "__main__":
    unittest.main()
