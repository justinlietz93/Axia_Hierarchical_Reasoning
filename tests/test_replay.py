from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.presentation.cli import main
from axia.formation import FinalAnswer
from axia.operation import (
    form_final_synthesis_context,
    parse_final_synthesis_response,
    record_run_manifest,
    replay_run,
)
from axia.projection import ReplayFailure, replay_manifest_payload
from tests.test_run_manifest import _manifest


def _replayable_manifest():
    manifest = _manifest()
    context = form_final_synthesis_context(manifest)
    artifact = context.accepted_artifacts[0]
    text = artifact.artifact.payload["answer"]
    assert isinstance(text, str)
    final_answer: FinalAnswer = parse_final_synthesis_response(
        context,
        json.dumps(
            {
                "claims": [
                    {
                        "text": text,
                        "source_artifact_id": artifact.artifact_id.value,
                        "evidence_excerpt": "SQLite is a practical local-first default",
                    }
                ],
                "unresolved_caveats": [],
            }
        ),
    )
    return replace(manifest, final_answer=final_answer)


class ReplayTests(unittest.TestCase):
    def test_replays_saved_graph_validation_scores_and_final_artifact_selection(self) -> None:
        manifest = _replayable_manifest()
        replay = replay_manifest_payload(manifest.to_payload())

        self.assertEqual(replay.graph_order[:3], ("node_canonicalize", "node_constitute", "node_retrieve"))
        self.assertEqual(replay.node_decisions[0].node_id, "node_draft")
        self.assertTrue(replay.node_decisions[0].validation_accepted)
        self.assertEqual(replay.node_decisions[0].score_decision, "accept")
        self.assertEqual(replay.final_source_artifact_ids, ("artifact_draft",))

    def test_rejects_tampered_prompt_hashes_and_score_decisions(self) -> None:
        payload = _replayable_manifest().to_payload()
        prompt_tampered = deepcopy(payload)
        prompt_tampered["prompt_hashes"]["node_draft:attempt:1"] = "different"
        score_tampered = deepcopy(payload)
        score_tampered["node_results"][0]["scorecard"]["decision"] = "repair"

        with self.assertRaises(ReplayFailure) as prompt_failure:
            replay_manifest_payload(prompt_tampered)
        with self.assertRaises(ReplayFailure) as score_failure:
            replay_manifest_payload(score_tampered)

        self.assertEqual(prompt_failure.exception.kind, "replay_prompt_hash_mismatch")
        self.assertEqual(score_failure.exception.kind, "replay_score_decision_mismatch")

    def test_replays_a_persisted_run_through_the_operation_and_cli(self) -> None:
        manifest = _replayable_manifest()
        with TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "runs.sqlite3"
            store = SQLiteRunStore(database)
            record_run_manifest(manifest, store)
            replay = replay_run(manifest.run_id, store)
            store.close()

            output_path = str(database)
            from io import StringIO
            import contextlib

            output = StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(["replay", manifest.run_id.value, "--run-store", output_path])

        self.assertEqual(replay.final_source_artifact_ids, ("artifact_draft",))
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["final_source_artifact_ids"], ["artifact_draft"])


if __name__ == "__main__":
    unittest.main()
