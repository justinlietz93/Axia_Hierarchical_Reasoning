from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Protocol

from axia.boundary.ports.model_provider import ModelMessage, ModelProvider, ModelRequest
from axia.benchmark.evidence import BenchmarkControlEvidence
from axia.benchmark.scorecard import BenchmarkScorecard
from axia.benchmark.suite import BenchmarkTask
from axia.shared.ids import RunId, stable_text_hash


BENCHMARK_MODES = ("single_shot", "quick", "standard")


@dataclass(frozen=True)
class BenchmarkExecution:
    """One saved benchmark output from a declared mode runner."""

    task_id: str
    mode: str
    run_id: RunId
    output: str
    scorecard: Mapping[str, object] | None
    metadata: Mapping[str, str]
    control_evidence: BenchmarkControlEvidence | None = None
    benchmark_scorecard: BenchmarkScorecard | None = None

    def __post_init__(self) -> None:
        if self.mode not in BENCHMARK_MODES or not self.task_id.strip() or not self.output.strip():
            raise ValueError("benchmark executions require an admitted mode, task ID, and non-empty output")
        if any(not key.strip() or not value.strip() for key, value in self.metadata.items()):
            raise ValueError("benchmark execution metadata keys and values must be non-empty strings")
        if self.benchmark_scorecard is not None and (
            self.benchmark_scorecard.task_id != self.task_id
            or self.benchmark_scorecard.mode != self.mode
            or self.benchmark_scorecard.source_run_id != self.run_id
        ):
            raise ValueError("benchmark scorecards must belong to the execution they score")

    def with_benchmark_scorecard(self, scorecard: BenchmarkScorecard) -> BenchmarkExecution:
        """Attach a comparison scorecard while preserving the execution's run-local scorecard."""

        return replace(self, benchmark_scorecard=scorecard)

    def to_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "run_id": self.run_id.value,
            "output": self.output,
            "scorecard": dict(self.scorecard) if self.scorecard is not None else None,
            "metadata": dict(sorted(self.metadata.items())),
            "control_evidence": self.control_evidence.to_payload() if self.control_evidence is not None else None,
            "benchmark_scorecard": self.benchmark_scorecard.to_payload() if self.benchmark_scorecard is not None else None,
        }


class BenchmarkRunner(Protocol):
    mode: str

    def execute(self, task: BenchmarkTask) -> BenchmarkExecution:
        """Execute one fixed benchmark task through the runner's declared mode."""


class AxiaBenchmarkExecutor(Protocol):
    def execute(self, task: BenchmarkTask, mode: str) -> BenchmarkExecution:
        """Execute one task through an Axia quick or standard reasoning path."""


@dataclass(frozen=True)
class SingleShotBenchmarkRunner:
    """One provider call baseline with no Axia decomposition, validation, or repair steps."""

    provider: ModelProvider
    profile_name: str
    mode: str = "single_shot"

    def execute(self, task: BenchmarkTask) -> BenchmarkExecution:
        prompt = "\n\n".join(
            (
                "ROLE\nAnswer the request directly in one pass.",
                "REQUEST\n" + task.request,
                "DELIVERABLE\n" + task.deliverable_type,
                "OUTPUT_FORMAT\n" + task.output_format,
                "CONSTRAINTS\n" + "\n".join(f"- {constraint}" for constraint in task.constraints),
            )
        )
        response = self.provider.generate(
            ModelRequest(
                messages=(ModelMessage(role="user", content=prompt),),
                metadata={"stage": "benchmark_single_shot", "task_id": task.task_id, "profile": self.profile_name},
            )
        )
        return BenchmarkExecution(
            task_id=task.task_id,
            mode=self.mode,
            run_id=_benchmark_run_id(task.task_id, self.mode),
            output=response.text,
            scorecard=None,
            metadata={"profile": self.profile_name, **dict(response.metadata)},
        )


@dataclass(frozen=True)
class AxiaModeBenchmarkRunner:
    """An explicit adapter around the real quick or standard Axia execution path."""

    mode: str
    executor: AxiaBenchmarkExecutor

    def __post_init__(self) -> None:
        if self.mode not in {"quick", "standard"}:
            raise ValueError("Axia benchmark runners support only quick or standard modes")

    def execute(self, task: BenchmarkTask) -> BenchmarkExecution:
        execution = self.executor.execute(task, self.mode)
        if execution.mode != self.mode or execution.task_id != task.task_id:
            raise ValueError("Axia benchmark executor returned an execution for a different task or mode")
        return execution


def _benchmark_run_id(task_id: str, mode: str) -> RunId:
    return RunId.from_value(f"run_benchmark_{mode}_{stable_text_hash(task_id)[:16]}")
