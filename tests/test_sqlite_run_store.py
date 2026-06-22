from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.ports.run_store import (
    RunManifestRecord,
    RunStoreFailure,
    RunTraceRecord,
)
from axia.shared.ids import RunId


class SQLiteRunStoreTests(unittest.TestCase):
    def test_persists_every_admitted_run_trace_category_in_order(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "runs.sqlite3"
            run_id = RunId.from_value("run_trace")
            store = SQLiteRunStore(database)
            store.create_run(
                RunManifestRecord(
                    run_id=run_id,
                    created_at="2026-06-19T00:00:00Z",
                    status="running",
                    mode="standard",
                    request_hash="request-hash",
                    payload={"schema_version": 1, "profile": "tiny-default"},
                )
            )

            kinds = ("node", "artifact", "scorecard", "error", "context", "memory_candidate")
            stored_records = [
                store.append(
                    RunTraceRecord(
                        run_id=run_id,
                        kind=kind,
                        record_id=f"{kind}-1",
                        payload={"kind": kind, "run_id": run_id.value},
                    )
                )
                for kind in kinds
            ]

            reloaded_store = SQLiteRunStore(database)
            stored_run = reloaded_store.read_run(run_id)

        self.assertEqual([record.sequence for record in stored_records], [1, 2, 3, 4, 5, 6])
        self.assertEqual(stored_run.manifest.request_hash, "request-hash")
        self.assertEqual([record.kind for record in stored_run.records], list(kinds))
        self.assertEqual(stored_run.records[-1].payload, {"kind": "memory_candidate", "run_id": "run_trace"})

    def test_rejects_trace_records_without_a_run_envelope(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            store = SQLiteRunStore(Path(temporary_directory) / "runs.sqlite3")
            with self.assertRaises(RunStoreFailure) as failure:
                store.append(
                    RunTraceRecord(
                        run_id=RunId.from_value("run_missing"),
                        kind="artifact",
                        record_id="artifact-1",
                        payload={"value": "orphan"},
                    )
                )

        self.assertEqual(failure.exception.kind, "run_not_found")

    def test_in_memory_store_keeps_its_run_trace_for_the_adapter_lifetime(self) -> None:
        store = SQLiteRunStore(":memory:")
        run_id = RunId.from_value("run_memory")
        store.create_run(
            RunManifestRecord(
                run_id=run_id,
                created_at="2026-06-19T00:00:00Z",
                status="running",
                mode="quick",
                request_hash="request-hash",
                payload={"schema_version": 1},
            )
        )

        self.assertEqual(store.read_run(run_id).manifest.run_id, run_id)
        store.close()

    def test_memory_candidates_are_only_available_through_their_originating_run(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            store = SQLiteRunStore(Path(temporary_directory) / "runs.sqlite3")
            first_run = RunId.from_value("run_first")
            second_run = RunId.from_value("run_second")
            for run_id in (first_run, second_run):
                store.create_run(
                    RunManifestRecord(
                        run_id=run_id,
                        created_at="2026-06-19T00:00:00Z",
                        status="complete",
                        mode="standard",
                        request_hash=run_id.value,
                        payload={"schema_version": 1},
                    )
                )
            store.append(
                RunTraceRecord(
                    run_id=first_run,
                    kind="memory_candidate",
                    record_id="candidate-1",
                    payload={"content": "candidate only"},
                )
            )

            first_trace = store.read_run(first_run)
            second_trace = store.read_run(second_run)

        self.assertEqual([record.kind for record in first_trace.records], ["memory_candidate"])
        self.assertEqual(second_trace.records, ())
        self.assertFalse(hasattr(store, "search_memory"))

    def test_rejects_unknown_trace_kinds(self) -> None:
        with self.assertRaises(ValueError):
            RunTraceRecord(
                run_id=RunId.from_value("run_trace"),
                kind="durable_memory",
                record_id="forbidden",
                payload={},
            )


if __name__ == "__main__":
    unittest.main()
