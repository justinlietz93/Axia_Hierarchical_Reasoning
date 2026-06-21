from __future__ import annotations

from axia.boundary.ports.run_store import RunStore
from axia.projection.replay import ReplayResult, replay_manifest_payload
from axia.shared.ids import RunId


def replay_run(run_id: RunId, run_store: RunStore) -> ReplayResult:
    """Reproduce one run's controller decisions from its locally stored manifest."""

    stored_run = run_store.read_run(run_id)
    return replay_manifest_payload(stored_run.manifest.payload)
