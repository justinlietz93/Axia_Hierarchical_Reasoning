from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from axia.benchmark.scorecard import BenchmarkScorecard


ADVANCED_STRATEGY_NAMES = frozenset({"self_consistency", "verifier_guided_selection", "branch_search", "multi_branch_synthesis"})


@dataclass(frozen=True)
class StrategyCandidate:
    """An experimental reasoning strategy with a declared bounded trial contract."""

    name: str
    max_model_calls: int
    max_branches: int
    required_artifact_kinds: tuple[str, ...]
    status: str = "candidate"

    def __post_init__(self) -> None:
        if self.name not in ADVANCED_STRATEGY_NAMES or self.status != "candidate":
            raise ValueError("advanced strategies remain named candidates until explicit admission")
        if self.max_model_calls <= 0 or self.max_branches <= 0 or not self.required_artifact_kinds:
            raise ValueError("candidate strategies require positive budgets and inspectable artifact kinds")


@dataclass(frozen=True)
class CandidateTrial:
    """One paired standard-versus-candidate benchmark observation."""

    task_id: str
    standard_scorecard: BenchmarkScorecard
    candidate_scorecard: BenchmarkScorecard
    model_calls: int
    artifact_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.task_id.strip() or self.standard_scorecard.mode != "standard":
            raise ValueError("candidate trials require a task ID and a standard-graph scorecard")
        if self.model_calls <= 0 or any(not kind.strip() for kind in self.artifact_kinds):
            raise ValueError("candidate trials require a positive call count and inspectable artifact kinds")


@dataclass(frozen=True)
class StrategyAdmissionResult:
    strategy_name: str
    admitted: bool
    median_score_delta: float
    required_median_delta: float
    rejection_reasons: tuple[str, ...]


def evaluate_strategy_admission(
    candidate: StrategyCandidate,
    trials: tuple[CandidateTrial, ...],
    *,
    required_median_delta: float = 0.01,
) -> StrategyAdmissionResult:
    """Admit a candidate only when bounded, inspectable trials beat the standard graph."""

    if not 0 < required_median_delta <= 1 or not trials:
        raise ValueError("admission requires trials and a median delta within (0, 1]")
    if len({trial.task_id for trial in trials}) != len(trials):
        raise ValueError("candidate admission trials require unique task IDs")
    reasons: list[str] = []
    deltas = []
    required_artifacts = set(candidate.required_artifact_kinds)
    for trial in trials:
        if trial.model_calls > candidate.max_model_calls:
            reasons.append("call_budget_exceeded")
        if not required_artifacts.issubset(set(trial.artifact_kinds)):
            reasons.append("required_artifacts_missing")
        if trial.candidate_scorecard.mode == "standard":
            reasons.append("candidate_mode_not_distinct")
        deltas.append(trial.candidate_scorecard.overall - trial.standard_scorecard.overall)
    median_delta = median(deltas)
    if median_delta < required_median_delta:
        reasons.append("median_improvement_not_met")
    rejection_reasons = tuple(sorted(set(reasons)))
    return StrategyAdmissionResult(
        strategy_name=candidate.name,
        admitted=not rejection_reasons,
        median_score_delta=median_delta,
        required_median_delta=required_median_delta,
        rejection_reasons=rejection_reasons,
    )
