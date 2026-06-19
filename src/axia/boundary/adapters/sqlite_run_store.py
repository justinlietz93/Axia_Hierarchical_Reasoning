from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from axia.boundary.ports.run_store import (
    RunManifestRecord,
    RunStoreFailure,
    RunTraceRecord,
    StoredRun,
    StoredRunTraceRecord,
)
from axia.shared.ids import RunId


class SQLiteRunStore:
    """Local SQLite storage for replayable, run-scoped trace evidence."""

    def __init__(self, database: str | Path) -> None:
        self._database = str(database)
        if self._database != ":memory:":
            Path(self._database).parent.mkdir(parents=True, exist_ok=True)
        self._connection = self._open_connection()
        self._initialize()

    def close(self) -> None:
        """Release the local SQLite connection when the composition root is done."""

        self._connection.close()

    def create_run(self, manifest: RunManifestRecord) -> None:
        manifest_json = _encode_json(manifest.payload, "run_manifest_not_serializable")
        with self._connection as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO runs(run_id, created_at, status, mode, request_hash, manifest_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.run_id.value,
                        manifest.created_at,
                        manifest.status,
                        manifest.mode,
                        manifest.request_hash,
                        manifest_json,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise RunStoreFailure(
                    kind="run_already_exists",
                    message=f"run {manifest.run_id} already exists",
                ) from error

    def append(self, record: RunTraceRecord) -> StoredRunTraceRecord:
        payload_json = _encode_json(record.payload, "run_trace_not_serializable")
        with self._connection as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT 1 FROM runs WHERE run_id = ?",
                    (record.run_id.value,),
                ).fetchone()
                if exists is None:
                    raise RunStoreFailure(
                        kind="run_not_found",
                        message=f"cannot append trace evidence to unknown run {record.run_id}",
                    )

                sequence = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM trace_records WHERE run_id = ?",
                    (record.run_id.value,),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO trace_records(run_id, sequence, kind, record_id, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (record.run_id.value, sequence, record.kind, record.record_id, payload_json),
                )
                connection.commit()
            except RunStoreFailure:
                connection.rollback()
                raise
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise RunStoreFailure(
                    kind="run_trace_conflict",
                    message=f"trace record {record.record_id!r} already exists for run {record.run_id}",
                ) from error

        return StoredRunTraceRecord(
            run_id=record.run_id,
            kind=record.kind,
            record_id=record.record_id,
            payload=dict(record.payload),
            sequence=sequence,
        )

    def read_run(self, run_id: RunId) -> StoredRun:
        with self._connection as connection:
            manifest_row = connection.execute(
                """
                SELECT created_at, status, mode, request_hash, manifest_json
                FROM runs
                WHERE run_id = ?
                """,
                (run_id.value,),
            ).fetchone()
            if manifest_row is None:
                raise RunStoreFailure(kind="run_not_found", message=f"run {run_id} does not exist")

            trace_rows = connection.execute(
                """
                SELECT sequence, kind, record_id, payload_json
                FROM trace_records
                WHERE run_id = ?
                ORDER BY sequence ASC
                """,
                (run_id.value,),
            ).fetchall()

        manifest = RunManifestRecord(
            run_id=run_id,
            created_at=manifest_row[0],
            status=manifest_row[1],
            mode=manifest_row[2],
            request_hash=manifest_row[3],
            payload=_decode_json(manifest_row[4]),
        )
        records = tuple(
            StoredRunTraceRecord(
                run_id=run_id,
                sequence=row[0],
                kind=row[1],
                record_id=row[2],
                payload=_decode_json(row[3]),
            )
            for row in trace_rows
        )
        return StoredRun(manifest=manifest, records=records)

    def _initialize(self) -> None:
        with self._connection as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    manifest_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trace_records (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    UNIQUE (run_id, kind, record_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                """
            )

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _encode_json(payload: object, failure_kind: str) -> str:
    try:
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise RunStoreFailure(
            kind=failure_kind,
            message="run-store payloads must be JSON serializable",
        ) from error


def _decode_json(payload: str) -> dict[str, object]:
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise RunStoreFailure(
            kind="run_store_schema_invalid",
            message="stored run payload must decode to a JSON object",
        )
    return decoded
