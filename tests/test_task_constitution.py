from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from axia.formation import (
    ConstitutionLimits,
    TaskConstitutionFailure,
    build_task_constitution,
    require_refinement_limits,
    require_task_constitution,
)
from axia.formation.canonical_request import CanonicalRequest


def _canonical_request(source_hash: str = "request-hash") -> CanonicalRequest:
    return CanonicalRequest(
        source_request_hash=source_hash,
        intent="compare database options",
        deliverable_type="technical recommendation",
        constraints=("local-first", "practical tradeoffs"),
        unknowns=("expected data volume",),
        risk_flags=("recommendation depends on scale",),
        output_format="concise comparison with recommendation",
        expected_depth="standard",
        needed_context=("project architecture", "storage needs"),
    )


class TaskConstitutionTests(unittest.TestCase):
    def test_builds_an_explicit_bounded_contract(self) -> None:
        constitution = build_task_constitution(_canonical_request())

        self.assertEqual(constitution.revision, 1)
        self.assertIsNone(constitution.previous_revision_hash)
        self.assertEqual(constitution.allowed_operations, ("context_provider",))
        self.assertEqual(constitution.limits.max_model_calls, 16)
        self.assertEqual(constitution.limits.max_seconds, 300)
        self.assertTrue(constitution.stop_conditions)
        self.assertTrue(constitution.quality_rubric)

    def test_brief_mode_reserves_time_for_bounded_cpu_local_retries(self) -> None:
        brief_request = CanonicalRequest(
            **{**_canonical_request().to_payload(), "source_request_hash": "request-hash", "expected_depth": "brief"}
        )
        constitution = build_task_constitution(brief_request)

        self.assertEqual(constitution.limits.max_model_calls, 6)
        self.assertEqual(constitution.limits.max_retries_per_node, 1)
        self.assertEqual(constitution.limits.max_seconds, 180)

    def test_constitution_is_immutable_and_revisions_are_explicit(self) -> None:
        initial = build_task_constitution(_canonical_request())
        with self.assertRaises(FrozenInstanceError):
            initial.mission = "changed"  # type: ignore[misc]

        revised = build_task_constitution(_canonical_request(), previous=initial)

        self.assertEqual(revised.revision, 2)
        self.assertEqual(revised.previous_revision_hash, initial.revision_hash())

    def test_rejects_revision_from_a_different_source_request(self) -> None:
        initial = build_task_constitution(_canonical_request())
        with self.assertRaises(TaskConstitutionFailure) as failure:
            build_task_constitution(_canonical_request("other-request"), previous=initial)

        self.assertEqual(failure.exception.kind, "task_constitution_revision_source_mismatch")

    def test_work_graph_and_refinement_require_a_bounded_constitution(self) -> None:
        with self.assertRaises(TaskConstitutionFailure) as graph_failure:
            require_task_constitution(None)
        with self.assertRaises(TaskConstitutionFailure) as refinement_failure:
            require_refinement_limits(None)

        self.assertEqual(graph_failure.exception.kind, "task_constitution_required")
        self.assertEqual(refinement_failure.exception.kind, "task_constitution_required")

    def test_rejects_missing_or_invalid_run_limits(self) -> None:
        with self.assertRaises(TaskConstitutionFailure) as failure:
            ConstitutionLimits(max_depth=4, max_model_calls=16, max_retries_per_node=0, max_seconds=300)

        self.assertEqual(failure.exception.kind, "task_constitution_invalid_limits")


if __name__ == "__main__":
    unittest.main()
