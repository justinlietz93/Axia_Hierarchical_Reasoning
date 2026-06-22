from __future__ import annotations

from dataclasses import replace
import unittest

from axia import __version__
from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.formation import (
    ScoreDimension,
    ScorePolicy,
    Scorecard,
    TypedArtifact,
    build_standard_work_graph,
    build_task_constitution,
    canonical_request_from_payload,
)
from axia.operation import record_run_manifest
from axia.projection import (
    RUN_MANIFEST_SCHEMA,
    ModelProfileIdentity,
    RunManifest,
    RunManifestFailure,
    RunManifestNodeResult,
    prompt_hash_key,
)
from axia.shared.ids import ArtifactId, CandidateId, NodeId, RunId, ScorecardId, stable_text_hash
from axia.source import ProviderResponseRecord, RequestRecord
from axia.formation.memory_candidate import MemoryCandidate


def _canonical_request():
    request = RequestRecord.from_text("Compare database options for a local-first AI tool.")
    return canonical_request_from_payload(
        request,
        {
            "intent": "compare database options",
            "deliverable_type": "technical recommendation",
            "constraints": ["local-first"],
            "unknowns": [],
            "risk_flags": [],
            "output_format": "concise recommendation",
            "expected_depth": "standard",
            "needed_context": [],
        },
    )


def _scorecard(run_id: RunId, node_id: NodeId, artifact_id: ArtifactId) -> Scorecard:
    dimensions = tuple(
        ScoreDimension(name=name, score=1.0, reason="checked", repair_instruction=None)
        for name in (
            "relevance",
            "completeness",
            "consistency",
            "specificity",
            "evidence_use",
            "constraint_compliance",
            "final_usability",
        )
    )
    return Scorecard(
        scorecard_id=ScorecardId.from_value("scorecard_draft"),
        source_run_id=run_id,
        source_node_id=node_id,
        source_artifact_id=artifact_id,
        dimensions=dimensions,
        overall=1.0,
        decision="accept",
    )


def _manifest() -> RunManifest:
    canonical_request = _canonical_request()
    constitution = build_task_constitution(canonical_request)
    graph = build_standard_work_graph(constitution)
    run_id = RunId.from_value("run_manifest")
    node_id = NodeId.from_value("node_draft")
    artifact_id = ArtifactId.from_value("artifact_draft")
    artifact = TypedArtifact.from_payload(
        {"answer": "SQLite is a practical local-first default for the proposed reasoning tool."}
    )
    prompt_hash = stable_text_hash("draft prompt")
    result = RunManifestNodeResult(
        node_id=node_id,
        attempt=1,
        status="accepted",
        input_hash=stable_text_hash("draft context"),
        prompt_hash=prompt_hash,
        artifact_id=artifact_id,
        artifact=artifact,
        validation_errors=(),
        scorecard=_scorecard(run_id, node_id, artifact_id),
        provider_response=ProviderResponseRecord.from_response(
            '{"answer":"SQLite is a practical local-first default for the proposed reasoning tool."}',
            {"provider": "fake", "request_id": "fake-123", "response_id": "fake-456"},
        ),
        started_at="2026-06-20T00:00:00Z",
        ended_at="2026-06-20T00:00:01Z",
    )
    return RunManifest(
        run_id=run_id,
        created_at="2026-06-20T00:00:00Z",
        app_version=__version__,
        user_request_hash=canonical_request.source_request_hash,
        model_profile=ModelProfileIdentity(
            name="tiny-default",
            profile_hash=stable_text_hash("tiny-default-profile"),
            provider_metadata={"provider": "fake", "model": "fake-tiny"},
        ),
        prompt_hashes={prompt_hash_key(node_id, 1): prompt_hash},
        mode="standard",
        status="complete",
        canonical_request=canonical_request,
        constitution=constitution,
        work_graph=graph,
        node_results=(result,),
        final_answer="Use SQLite first; revisit the choice only when scale or multi-user requirements demand it.",
        memory_candidates=(
            MemoryCandidate(
                candidate_id=CandidateId.from_value("candidate_local_first_storage"),
                candidate_type="project",
                proposed_scope="project",
                content="The project prioritizes local-first run storage.",
                source_run_id=run_id,
                source_artifact_ids=(artifact_id,),
                confidence=0.82,
                reason="The accepted draft explicitly supports local-first storage.",
                caveats=(),
                created_at="2026-06-20T00:00:01Z",
                tags=("storage",),
            ),
        ),
        metrics={"model_calls": 1, "duration_seconds": 1.0},
    )


class RunManifestTests(unittest.TestCase):
    def test_projects_complete_versioned_replay_evidence_and_records_it(self) -> None:
        manifest = _manifest()
        payload = manifest.to_payload()
        store = SQLiteRunStore(":memory:")

        record_run_manifest(manifest, store)

        stored = store.read_run(manifest.run_id)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(set(RUN_MANIFEST_SCHEMA["required"]), set(payload))
        self.assertEqual(payload["model_profile"]["name"], "tiny-default")
        self.assertIn("node_draft:attempt:1", payload["prompt_hashes"])
        self.assertEqual(payload["node_results"][0]["provider_response"]["metadata"]["request_id"], "fake-123")
        self.assertEqual(payload["node_results"][0]["scorecard"]["source_artifact_id"], "artifact_draft")
        self.assertEqual(payload["memory_candidates"][0]["source_artifact_ids"], ["artifact_draft"])
        self.assertEqual(stored.manifest.payload, payload)

    def test_rejects_node_results_without_matching_prompt_trace_or_graph_lineage(self) -> None:
        manifest = _manifest()

        with self.assertRaises(RunManifestFailure) as prompt_failure:
            replace(manifest, prompt_hashes={})

        invalid_result = replace(manifest.node_results[0], node_id=NodeId.from_value("node_unknown"))
        with self.assertRaises(RunManifestFailure) as graph_failure:
            replace(manifest, node_results=(invalid_result,))

        self.assertEqual(prompt_failure.exception.kind, "run_manifest_prompt_hash_missing")
        self.assertEqual(graph_failure.exception.kind, "run_manifest_unknown_node")

    def test_rejects_complete_manifest_without_a_final_answer(self) -> None:
        with self.assertRaises(RunManifestFailure) as failure:
            replace(_manifest(), final_answer=None)

        self.assertEqual(failure.exception.kind, "run_manifest_final_answer_missing")


if __name__ == "__main__":
    unittest.main()
