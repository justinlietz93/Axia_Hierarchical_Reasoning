"""Fixed suites and runner contracts for measuring Axia reasoning improvement."""

from axia.benchmark.harness import BenchmarkFailure, run_benchmark_suite
from axia.benchmark.comparison import (
    MVP_MEDIAN_SCORE_DELTA,
    BenchmarkImprovementResult,
    compare_mvp_improvement,
)
from axia.benchmark.evidence import (
    BenchmarkControlEvidence,
    BenchmarkDecompositionStep,
    BenchmarkEvidenceSupport,
    BenchmarkRepairAttempt,
    BenchmarkReplayEvidence,
)
from axia.benchmark.report import BENCHMARK_REPORT_SCHEMA, BenchmarkRecord, BenchmarkReport
from axia.benchmark.runner import (
    BENCHMARK_MODES,
    AxiaBenchmarkExecutor,
    AxiaModeBenchmarkRunner,
    BenchmarkExecution,
    BenchmarkRunner,
    SingleShotBenchmarkRunner,
)
from axia.benchmark.scorecard import (
    BENCHMARK_SCORE_DIMENSIONS,
    BenchmarkDimensionScore,
    BenchmarkScoringConfiguration,
    BenchmarkScorecard,
)
from axia.benchmark.scoring import (
    AnswerUsefulnessAssessment,
    AnswerUsefulnessEvaluator,
    BenchmarkScorer,
    LexicalAnswerUsefulnessEvaluator,
    score_benchmark_report,
)
from axia.benchmark.suite import BASELINE_BENCHMARK_SUITE, BenchmarkSuite, BenchmarkTask

__all__ = [
    "BENCHMARK_MODES",
    "BENCHMARK_REPORT_SCHEMA",
    "BENCHMARK_SCORE_DIMENSIONS",
    "BASELINE_BENCHMARK_SUITE",
    "BenchmarkImprovementResult",
    "AnswerUsefulnessAssessment",
    "AnswerUsefulnessEvaluator",
    "AxiaBenchmarkExecutor",
    "AxiaModeBenchmarkRunner",
    "BenchmarkControlEvidence",
    "BenchmarkDecompositionStep",
    "BenchmarkDimensionScore",
    "BenchmarkEvidenceSupport",
    "BenchmarkExecution",
    "BenchmarkFailure",
    "BenchmarkRecord",
    "BenchmarkRepairAttempt",
    "BenchmarkReplayEvidence",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkScorecard",
    "BenchmarkScoringConfiguration",
    "BenchmarkScorer",
    "BenchmarkSuite",
    "BenchmarkTask",
    "LexicalAnswerUsefulnessEvaluator",
    "MVP_MEDIAN_SCORE_DELTA",
    "SingleShotBenchmarkRunner",
    "run_benchmark_suite",
    "compare_mvp_improvement",
    "score_benchmark_report",
]
