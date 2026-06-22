from __future__ import annotations

import json
from threading import Thread
import unittest
from urllib.request import urlopen

from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.presentation.local_web import create_local_web_server
from axia.operation import record_run_manifest
from tests.test_replay import _replayable_manifest


class LocalWebTests(unittest.TestCase):
    def test_serves_a_read_only_run_index_and_safe_run_detail(self) -> None:
        manifest = _replayable_manifest()
        store = SQLiteRunStore(":memory:")
        record_run_manifest(manifest, store)
        server = create_local_web_server(store, port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            index = urlopen(base_url + "/", timeout=2).read().decode("utf-8")
            runs = json.loads(urlopen(base_url + "/api/runs", timeout=2).read())
            detail = json.loads(urlopen(base_url + f"/api/runs/{manifest.run_id.value}", timeout=2).read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            store.close()

        self.assertIn("Axia Local Run Browser", index)
        self.assertEqual(runs["runs"][0]["run_id"], manifest.run_id.value)
        self.assertEqual(detail["status"], "complete")
        self.assertEqual(detail["completed_nodes"][0]["node_id"], "node_draft")
        self.assertEqual(detail["scorecards"][0]["decision"], "accept")
        self.assertEqual(detail["accepted_artifacts"][0]["artifact_id"], "artifact_draft")
        self.assertNotIn("provider_response", detail)


if __name__ == "__main__":
    unittest.main()
