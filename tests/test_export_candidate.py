from __future__ import annotations

import unittest

from axia.operation import emit_export_candidates, form_export_candidates
from tests.test_replay import _replayable_manifest


class ExternalCurationModule:
    def __init__(self) -> None:
        self.received = []

    def emit(self, candidate) -> None:
        self.received.append(candidate)


class ExportCandidateTests(unittest.TestCase):
    def test_forms_reasoning_and_training_candidates_from_accepted_trace(self) -> None:
        candidates = form_export_candidates(_replayable_manifest())
        self.assertEqual([candidate.candidate_type for candidate in candidates], ["reasoning_example", "training_slice"])
        self.assertEqual(candidates[0].source_artifact_ids[0].value, "artifact_draft")

    def test_external_delivery_requires_explicit_user_approval(self) -> None:
        candidates = form_export_candidates(_replayable_manifest())
        sink = ExternalCurationModule()
        with self.assertRaises(PermissionError):
            emit_export_candidates(candidates, sink)
        emitted = emit_export_candidates(candidates, sink, user_approved=True)
        self.assertEqual(tuple(sink.received), emitted)
