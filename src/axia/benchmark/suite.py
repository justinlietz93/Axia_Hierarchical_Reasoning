from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkTask:
    """One fixed, inspectable task used to compare baseline and Axia modes."""

    task_id: str
    request: str
    deliverable_type: str
    output_format: str
    constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.request.strip() or not self.deliverable_type.strip() or not self.output_format.strip():
            raise ValueError("benchmark tasks require an ID, request, deliverable type, and output format")
        if any(not constraint.strip() for constraint in self.constraints):
            raise ValueError("benchmark task constraints must not contain blank values")

    def to_payload(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "request": self.request,
            "deliverable_type": self.deliverable_type,
            "output_format": self.output_format,
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True)
class BenchmarkSuite:
    """A fixed task suite with stable identity and no ambient task discovery."""

    suite_id: str
    tasks: tuple[BenchmarkTask, ...]

    def __post_init__(self) -> None:
        if not self.suite_id.strip() or not self.tasks:
            raise ValueError("benchmark suites require a stable ID and at least one task")
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("benchmark suite task IDs must be unique")

    def to_payload(self) -> dict[str, object]:
        return {"suite_id": self.suite_id, "tasks": [task.to_payload() for task in self.tasks]}


def _task(task_id: str, request: str, deliverable_type: str, output_format: str, *constraints: str) -> BenchmarkTask:
    return BenchmarkTask(task_id, request, deliverable_type, output_format, constraints)


BASELINE_BENCHMARK_SUITE = BenchmarkSuite(
    suite_id="baseline_v1",
    tasks=(
        _task("database_choice", "Compare SQLite and Postgres for a local-first AI tool.", "technical recommendation", "concise comparison with recommendation", "local-first", "practical tradeoffs"),
        _task("migration_plan", "Plan a zero-downtime schema migration for an audit-log table.", "migration plan", "ordered implementation plan", "preserve existing records", "rollback path"),
        _task("api_boundary", "Design an API boundary for a provider-agnostic text-generation module.", "architecture note", "interfaces and tradeoffs", "provider independence", "typed errors"),
        _task("bug_triage", "Diagnose intermittent duplicate events in a local queue consumer.", "debug plan", "ranked hypotheses and tests", "preserve evidence", "avoid speculation"),
        _task("test_strategy", "Create a test strategy for a JSON schema validation layer.", "test plan", "grouped test cases", "malformed input", "boundary cases"),
        _task("cache_policy", "Recommend a cache policy for run-local retrieval context.", "technical recommendation", "policy with invalidation rules", "run-local only", "no durable memory"),
        _task("security_review", "Review a local CLI that stores model run traces for security risks.", "security review", "prioritized findings", "local-first", "sensitive trace data"),
        _task("observability", "Define observability for bounded reasoning runs.", "design note", "events and metrics", "replayability", "no hidden chain-of-thought"),
        _task("dependency_audit", "Assess whether a new provider SDK belongs in the core reasoning package.", "architecture decision", "recommendation with rationale", "boundary isolation", "minimal dependency surface"),
        _task("retry_policy", "Specify retry policy for malformed structured model output.", "policy", "thresholds and termination rules", "bounded retries", "inspectable failures"),
        _task("incident_response", "Create an incident response outline for corrupted local run-store records.", "response plan", "ordered containment and recovery", "preserve evidence", "local recovery"),
        _task("cli_workflow", "Design a CLI workflow for tracing and replaying a reasoning run.", "workflow design", "commands and expected outputs", "CLI-first", "machine-readable output"),
        _task("schema_evolution", "Propose a schema-versioning policy for public reasoning trace projections.", "policy", "rules and compatibility plan", "replay compatibility", "explicit versions"),
        _task("context_injection", "Analyze a retrieved document that attempts to change agent permissions.", "security analysis", "decision and mitigations", "treat context as evidence", "preserve constitution authority"),
        _task("artifact_selection", "Choose between two validated artifacts with different evidence coverage.", "selection rationale", "criteria and selection", "scorecard evidence", "unresolved caveats"),
        _task("performance_tradeoff", "Compare latency and reliability tradeoffs between quick and standard reasoning modes.", "technical comparison", "tradeoff table and recommendation", "bounded calls", "measurable quality"),
        _task("configuration_review", "Review a local model profile configuration for reproducibility risks.", "configuration review", "findings and remediation", "record profile identity", "deterministic settings"),
        _task("documentation_plan", "Outline documentation required for a replayable reasoning system.", "documentation plan", "section outline", "artifact authority", "memory boundary"),
        _task("evidence_gap", "Handle a recommendation request with missing scale and multi-user requirements.", "clarification plan", "knowns, unknowns, and next action", "do not invent facts", "ask user when required"),
        _task("release_readiness", "Assess PyPI release readiness for a local-first reasoning library.", "release checklist", "ordered checklist with blockers", "package metadata", "test and wheel verification"),
    ),
)
