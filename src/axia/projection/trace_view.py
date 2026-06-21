from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.projection.replay import ReplayResult, replay_manifest_payload
from axia.shared.errors import AxiaError


TRACE_VIEW_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "run_id",
        "status",
        "request_interpretation",
        "task_contract",
        "graph_order",
        "scoped_context_records",
        "draft_score",
        "repair_summary",
        "verification_result",
        "final_acceptance",
        "errors",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "run_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "request_interpretation": {"type": "object"},
        "task_contract": {"type": "object"},
        "graph_order": {"type": "array", "items": {"type": "string"}},
        "scoped_context_records": {"type": "array"},
        "draft_score": {},
        "repair_summary": {"type": "array"},
        "verification_result": {},
        "final_acceptance": {"type": "object"},
        "errors": {"type": "array"},
    },
}


@dataclass(frozen=True)
class TraceRecord:
    """One minimal run-trace input admitted to the projection layer."""

    sequence: int
    kind: str
    record_id: str
    payload: Mapping[str, object]


@dataclass(frozen=True)
class TraceView:
    """A safe, versioned trace projection that excludes provider prose and context content."""

    run_id: str
    status: str
    request_interpretation: Mapping[str, object]
    task_contract: Mapping[str, object]
    graph_order: tuple[str, ...]
    scoped_context_records: tuple[Mapping[str, object], ...]
    draft_score: Mapping[str, object] | None
    repair_summary: tuple[Mapping[str, object], ...]
    verification_result: Mapping[str, object] | None
    final_acceptance: Mapping[str, object]
    errors: tuple[Mapping[str, object], ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise TraceViewFailure(kind="trace_view_schema_version_invalid", message="trace views currently require schema version 1")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "status": self.status,
            "request_interpretation": dict(self.request_interpretation),
            "task_contract": dict(self.task_contract),
            "graph_order": list(self.graph_order),
            "scoped_context_records": [dict(record) for record in self.scoped_context_records],
            "draft_score": dict(self.draft_score) if self.draft_score is not None else None,
            "repair_summary": [dict(summary) for summary in self.repair_summary],
            "verification_result": dict(self.verification_result) if self.verification_result is not None else None,
            "final_acceptance": dict(self.final_acceptance),
            "errors": [dict(error) for error in self.errors],
        }

    def render_text(self) -> str:
        lines = [
            f"Run: {self.run_id}",
            f"Status: {self.status}",
            f"Intent: {self.request_interpretation.get('intent', 'unknown')}",
            f"Deliverable: {self.task_contract.get('deliverable_definition', 'unknown')}",
            f"Graph: {' -> '.join(self.graph_order)}",
            f"Context records: {len(self.scoped_context_records)}",
            f"Repair attempts: {len(self.repair_summary)}",
            f"Errors: {len(self.errors)}",
        ]
        if self.draft_score is not None:
            lines.append(f"Draft score: {self.draft_score.get('decision', 'unscored')}")
        if self.verification_result is not None:
            lines.append(f"Verification: {self.verification_result.get('status', 'unknown')}")
        lines.append(f"Final acceptance: {self.final_acceptance.get('status', 'unknown')}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TraceViewFailure(AxiaError):
    """A deterministic failure while projecting a trace view from saved run evidence."""


def project_trace_view(
    manifest: Mapping[str, object],
    *,
    status: str,
    records: tuple[TraceRecord, ...],
) -> TraceView:
    """Project one stored run without exposing raw prompts, model prose, or context content."""

    replay = replay_manifest_payload(manifest)
    node_results = _object_list(manifest.get("node_results"), "trace_view_node_results_invalid")
    draft_score = _scorecard_for_node(node_results, "node_draft")
    repair_summary = tuple(_node_summary(result) for result in node_results if result.get("node_id") == "node_repair")
    verification_result = _node_summary_or_none(node_results, "node_verify")
    return TraceView(
        run_id=replay.run_id,
        status=status,
        request_interpretation=_mapping(manifest.get("canonical_request"), "trace_view_manifest_invalid"),
        task_contract=_mapping(manifest.get("constitution"), "trace_view_manifest_invalid"),
        graph_order=replay.graph_order,
        scoped_context_records=tuple(_context_record(record) for record in records if record.kind == "context"),
        draft_score=draft_score,
        repair_summary=repair_summary,
        verification_result=verification_result,
        final_acceptance=_final_acceptance(status, replay),
        errors=tuple(_error_record(record) for record in records if record.kind == "error"),
    )


def _scorecard_for_node(node_results: tuple[Mapping[str, object], ...], node_id: str) -> Mapping[str, object] | None:
    for result in node_results:
        if result.get("node_id") == node_id:
            scorecard = result.get("scorecard")
            return _mapping(scorecard, "trace_view_scorecard_invalid") if scorecard is not None else None
    return None


def _node_summary_or_none(node_results: tuple[Mapping[str, object], ...], node_id: str) -> Mapping[str, object] | None:
    for result in node_results:
        if result.get("node_id") == node_id:
            return _node_summary(result)
    return None


def _node_summary(result: Mapping[str, object]) -> Mapping[str, object]:
    scorecard = result.get("scorecard")
    return {
        "node_id": result.get("node_id"),
        "attempt": result.get("attempt"),
        "status": result.get("status"),
        "validation_error_count": len(_list(result.get("validation_errors"), "trace_view_node_result_invalid")),
        "decision": _mapping(scorecard, "trace_view_scorecard_invalid").get("decision") if scorecard is not None else None,
    }


def _context_record(record: TraceRecord) -> Mapping[str, object]:
    payload = record.payload
    references = _object_list(payload.get("references", []), "trace_view_context_invalid")
    return {
        "sequence": record.sequence,
        "record_id": record.record_id,
        "node_id": payload.get("node_id"),
        "references": [
            {
                "scope": reference.get("scope"),
                "source_type": reference.get("source_type"),
                "reference_id": reference.get("reference_id"),
                "content_hash": reference.get("content_hash"),
                "accepted": reference.get("accepted"),
            }
            for reference in references
        ],
    }


def _error_record(record: TraceRecord) -> Mapping[str, object]:
    return {
        "sequence": record.sequence,
        "record_id": record.record_id,
        "kind": record.payload.get("kind"),
        "message": record.payload.get("message"),
    }


def _final_acceptance(status: str, replay: ReplayResult) -> Mapping[str, object]:
    return {
        "status": status,
        "final_source_artifact_ids": list(replay.final_source_artifact_ids),
        "final_answer": replay.final_answer,
    }


def _mapping(value: object, kind: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TraceViewFailure(kind=kind, message="trace evidence must be an object")
    return value


def _object_list(value: object, kind: str) -> tuple[Mapping[str, object], ...]:
    return tuple(_mapping(item, kind) for item in _list(value, kind))


def _list(value: object, kind: str) -> list[object]:
    if not isinstance(value, list):
        raise TraceViewFailure(kind=kind, message="trace evidence must be an array")
    return value
