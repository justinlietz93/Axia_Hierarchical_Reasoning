from __future__ import annotations

import contextlib
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.presentation.cli import main
from axia.boundary.ports.run_store import RunTraceRecord
from axia.operation import project_run_trace, record_run_manifest
from axia.projection import TRACE_VIEW_SCHEMA
from axia.source import ProviderResponseRecord
from tests.test_replay import _replayable_manifest


class TraceViewTests(unittest.TestCase):
    def test_projects_machine_readable_trace_without_provider_or_context_content(self) -> None:
        manifest = _replayable_manifest()
        hidden_provider_text = "private hidden reasoning must not appear in a trace view"
        node_result = replace(
            manifest.node_results[0],
            provider_response=ProviderResponseRecord.from_response(hidden_provider_text, {"provider": "fake"}),
        )
        manifest = replace(manifest, node_results=(node_result,))
        store = SQLiteRunStore(":memory:")
        record_run_manifest(manifest, store)
        store.append(
            RunTraceRecord(
                run_id=manifest.run_id,
                kind="context",
                record_id="context_draft",
                payload={
                    "node_id": "node_draft",
                    "references": [
                        {
                            "scope": "retrieved_evidence",
                            "source_type": "evidence",
                            "reference_id": "evidence_1",
                            "content": "untrusted retrieved text must not appear in trace output",
                            "content_hash": "hash_1",
                            "accepted": True,
                        }
                    ],
                },
            )
        )
        store.append(
            RunTraceRecord(
                run_id=manifest.run_id,
                kind="error",
                record_id="error_retry",
                payload={"kind": "provider_timeout", "message": "retry recorded"},
            )
        )

        trace = project_run_trace(manifest.run_id, store)
        payload = trace.to_payload()
        encoded = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(set(TRACE_VIEW_SCHEMA["required"]), set(payload))
        self.assertEqual(payload["request_interpretation"]["intent"], "compare database options")
        self.assertEqual(payload["task_contract"]["deliverable_definition"], "technical recommendation: concise recommendation")
        self.assertEqual(payload["draft_score"]["decision"], "accept")
        self.assertEqual(payload["final_acceptance"]["final_source_artifact_ids"], ["artifact_draft"])
        self.assertEqual(payload["scoped_context_records"][0]["references"][0]["reference_id"], "evidence_1")
        self.assertNotIn("content", payload["scoped_context_records"][0]["references"][0])
        self.assertNotIn(hidden_provider_text, encoded)
        self.assertNotIn("untrusted retrieved text", encoded)

    def test_cli_renders_json_and_text_from_the_same_stored_trace(self) -> None:
        manifest = _replayable_manifest()
        with TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "runs.sqlite3"
            store = SQLiteRunStore(database)
            record_run_manifest(manifest, store)
            store.close()

            json_output = StringIO()
            with contextlib.redirect_stdout(json_output):
                json_exit = main(["trace", manifest.run_id.value, "--run-store", str(database)])
            text_output = StringIO()
            with contextlib.redirect_stdout(text_output):
                text_exit = main(["trace", manifest.run_id.value, "--run-store", str(database), "--format", "text"])

        self.assertEqual(json_exit, 0)
        self.assertEqual(text_exit, 0)
        self.assertEqual(json.loads(json_output.getvalue())["run_id"], manifest.run_id.value)
        self.assertIn("Run: run_manifest", text_output.getvalue())


if __name__ == "__main__":
    unittest.main()
