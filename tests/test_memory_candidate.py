from __future__ import annotations

import inspect
import unittest

from axia.formation import MEMORY_CANDIDATE_SCHEMA, MemoryCandidate, MemoryCandidateFailure
from axia.operation import emit_memory_candidate
from axia.shared.ids import ArtifactId, CandidateId, RunId


def _candidate() -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id=CandidateId.from_value("candidate_database_choice"),
        candidate_type="project",
        proposed_scope="project",
        content="The project prefers local-first storage for run traces.",
        source_run_id=RunId.from_value("run_reasoning"),
        source_artifact_ids=(ArtifactId.from_value("artifact_final"),),
        confidence=0.82,
        reason="The accepted final artifact states the project constraint.",
        caveats=("Validate this preference with the project owner.",),
        created_at="2026-06-20T00:00:00Z",
        tags=("storage", "local-first"),
    )


class MemoryCandidateTests(unittest.TestCase):
    def test_forms_a_versioned_projection_with_complete_lineage(self) -> None:
        candidate = _candidate()

        self.assertEqual(candidate.to_payload()["schema_version"], 1)
        self.assertEqual(candidate.to_payload()["source_run_id"], "run_reasoning")
        self.assertEqual(candidate.to_payload()["source_artifact_ids"], ["artifact_final"])
        self.assertEqual(MEMORY_CANDIDATE_SCHEMA["properties"]["content"], {"type": "string", "minLength": 1})
        self.assertEqual(emit_memory_candidate(candidate), candidate)

    def test_rejects_invalid_candidate_lineage_and_confidence(self) -> None:
        with self.assertRaises(MemoryCandidateFailure) as lineage_failure:
            MemoryCandidate(
                candidate_id=CandidateId.from_value("candidate_missing_lineage"),
                candidate_type="fact",
                proposed_scope="run",
                content="candidate",
                source_run_id=RunId.from_value("run_reasoning"),
                source_artifact_ids=(),
                confidence=0.5,
                reason="test",
                caveats=(),
                created_at="2026-06-20T00:00:00Z",
                tags=(),
            )

        with self.assertRaises(MemoryCandidateFailure) as confidence_failure:
            MemoryCandidate(
                candidate_id=CandidateId.from_value("candidate_invalid_confidence"),
                candidate_type="fact",
                proposed_scope="run",
                content="candidate",
                source_run_id=RunId.from_value("run_reasoning"),
                source_artifact_ids=(ArtifactId.from_value("artifact_final"),),
                confidence=1.1,
                reason="test",
                caveats=(),
                created_at="2026-06-20T00:00:00Z",
                tags=(),
            )

        self.assertEqual(lineage_failure.exception.kind, "memory_candidate_missing_lineage")
        self.assertEqual(confidence_failure.exception.kind, "memory_candidate_confidence_invalid")

    def test_emission_has_no_durable_write_surface(self) -> None:
        emitted = emit_memory_candidate(_candidate())
        emitter_source = inspect.getsource(emit_memory_candidate)

        self.assertEqual(emitted, _candidate())
        self.assertNotIn("RunStore", emitter_source)
        self.assertNotIn("SQLite", emitter_source)
        self.assertNotIn("persist", emitter_source.lower())
        self.assertFalse(hasattr(emitted, "promote"))
        self.assertFalse(hasattr(emitted, "write"))


if __name__ == "__main__":
    unittest.main()
