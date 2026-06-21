from __future__ import annotations

from axia.boundary.ports.run_store import RunStore
from axia.projection.trace_view import TraceRecord, TraceView, project_trace_view
from axia.shared.ids import RunId


def project_run_trace(run_id: RunId, run_store: RunStore) -> TraceView:
    """Project one locally stored reasoning trace through the run-store boundary."""

    stored_run = run_store.read_run(run_id)
    return project_trace_view(
        stored_run.manifest.payload,
        status=stored_run.manifest.status,
        records=tuple(
            TraceRecord(
                sequence=record.sequence,
                kind=record.kind,
                record_id=record.record_id,
                payload=record.payload,
            )
            for record in stored_run.records
        ),
    )
