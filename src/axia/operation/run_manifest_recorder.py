from __future__ import annotations

from axia.boundary.ports.run_store import RunManifestRecord, RunStore
from axia.projection.run_manifest import RunManifest


def record_run_manifest(manifest: RunManifest, run_store: RunStore) -> None:
    """Create the local run envelope from one complete versioned manifest projection."""

    run_store.create_run(
        RunManifestRecord(
            run_id=manifest.run_id,
            created_at=manifest.created_at,
            status=manifest.status,
            mode=manifest.mode,
            request_hash=manifest.user_request_hash,
            payload=manifest.to_payload(),
        )
    )
