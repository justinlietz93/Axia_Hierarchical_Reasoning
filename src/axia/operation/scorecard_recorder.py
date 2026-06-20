from __future__ import annotations

from axia.boundary.ports.run_store import RunStore, RunTraceRecord, StoredRunTraceRecord
from axia.formation.scorecard import Scorecard


def record_scorecard(scorecard: Scorecard, run_store: RunStore) -> StoredRunTraceRecord:
    """Append one lineage-complete scorecard to the local reasoning trace."""

    return run_store.append(
        RunTraceRecord(
            run_id=scorecard.source_run_id,
            kind="scorecard",
            record_id=scorecard.scorecard_id.value,
            payload=scorecard.to_payload(),
        )
    )
