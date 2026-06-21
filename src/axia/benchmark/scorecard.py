from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.shared.ids import RunId, stable_json_hash


BENCHMARK_SCORE_DIMENSIONS = (
    "final_answer_usefulness",
    "task_decomposition_quality",
    "schema_validity",
    "constraint_compliance",
    "evidence_support",
    "repair_effectiveness",
    "replayability",
)


@dataclass(frozen=True)
class BenchmarkScoringConfiguration:
    """Stable identity and parameters for the evaluator shared by compared modes."""

    evaluator_id: str
    parameters: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.evaluator_id.strip():
            raise ValueError("benchmark scoring configuration requires an evaluator ID")
        if any(not key.strip() or not value.strip() for key, value in self.parameters.items()):
            raise ValueError("benchmark scoring configuration parameters must be non-empty strings")

    def to_payload(self) -> dict[str, object]:
        return {"evaluator_id": self.evaluator_id, "parameters": dict(sorted(self.parameters.items()))}


@dataclass(frozen=True)
class BenchmarkDimensionScore:
    """One benchmark criterion, including explicitly unassessed controls."""

    name: str
    score: float | None
    reason: str

    def __post_init__(self) -> None:
        if self.name not in BENCHMARK_SCORE_DIMENSIONS:
            raise ValueError(f"unsupported benchmark score dimension {self.name!r}")
        if self.score is not None and not 0 <= self.score <= 1:
            raise ValueError("benchmark dimension scores must be within [0, 1]")
        if not self.reason.strip():
            raise ValueError("benchmark dimension scores require a reason")

    def to_payload(self) -> dict[str, object]:
        return {"name": self.name, "score": self.score, "reason": self.reason}


@dataclass(frozen=True)
class BenchmarkScorecard:
    """Versioned comparison scorecard for one task-mode execution."""

    scorecard_id: str
    task_id: str
    mode: str
    source_run_id: RunId
    dimensions: tuple[BenchmarkDimensionScore, ...]
    overall: float
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("benchmark scorecards currently require schema version 1")
        if not self.scorecard_id.strip() or not self.task_id.strip() or not self.mode.strip():
            raise ValueError("benchmark scorecards require IDs and a mode")
        if len(self.dimensions) != len(BENCHMARK_SCORE_DIMENSIONS) or {
            dimension.name for dimension in self.dimensions
        } != set(BENCHMARK_SCORE_DIMENSIONS):
            raise ValueError("benchmark scorecards require every benchmark dimension exactly once")
        assessed = [dimension.score for dimension in self.dimensions if dimension.score is not None]
        if not assessed:
            raise ValueError("benchmark scorecards require at least one assessed dimension")
        expected_overall = sum(assessed) / len(assessed)
        if not 0 <= self.overall <= 1 or abs(self.overall - expected_overall) > 0.000001:
            raise ValueError("benchmark scorecard overall must match assessed dimension scores")

    @classmethod
    def from_dimensions(
        cls,
        *,
        task_id: str,
        mode: str,
        source_run_id: RunId,
        dimensions: tuple[BenchmarkDimensionScore, ...],
    ) -> BenchmarkScorecard:
        assessed = [dimension.score for dimension in dimensions if dimension.score is not None]
        if not assessed:
            raise ValueError("benchmark scorecards require at least one assessed dimension")
        identity = {
            "task_id": task_id,
            "mode": mode,
            "source_run_id": source_run_id.value,
            "dimensions": [dimension.to_payload() for dimension in dimensions],
        }
        return cls(
            scorecard_id=f"benchmark_scorecard_{stable_json_hash(identity)[:16]}",
            task_id=task_id,
            mode=mode,
            source_run_id=source_run_id,
            dimensions=dimensions,
            overall=sum(assessed) / len(assessed),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scorecard_id": self.scorecard_id,
            "task_id": self.task_id,
            "mode": self.mode,
            "source_run_id": self.source_run_id.value,
            "dimensions": [dimension.to_payload() for dimension in self.dimensions],
            "overall": self.overall,
            "assessed_dimension_count": sum(dimension.score is not None for dimension in self.dimensions),
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())
