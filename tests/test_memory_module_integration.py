from __future__ import annotations

import unittest

from axia.boundary.ports.context_provider import ContextQuery, ContextRecord, ContextResponse
from axia.operation import emit_memory_candidate, retrieve_context
from axia.shared.ids import NodeId, RunId
from tests.test_memory_candidate import _candidate


class ExternalMemoryModule:
    def __init__(self) -> None:
        self.received = []

    def retrieve(self, query: ContextQuery) -> ContextResponse:
        return ContextResponse((ContextRecord("memory_reference", {"content": "external memory evidence"}),))

    def emit(self, candidate) -> None:
        self.received.append(candidate)


def _query() -> ContextQuery:
    return ContextQuery(
        run_id=RunId.from_value("run_memory_integration"),
        node_id=NodeId.from_value("node_retrieve"),
        scope="retrieved_evidence",
        query="project constraint",
    )


class MemoryModuleIntegrationTests(unittest.TestCase):
    def test_external_module_can_supply_context_and_receive_candidates(self) -> None:
        module = ExternalMemoryModule()

        retrieval = retrieve_context(_query(), module)
        emitted = emit_memory_candidate(_candidate(), module)

        self.assertTrue(retrieval.provider_available)
        self.assertEqual(retrieval.evidence[0].reference_id, "memory_reference")
        self.assertEqual(module.received, [emitted])

    def test_reasoning_operations_remain_valid_without_a_memory_module(self) -> None:
        retrieval = retrieve_context(_query(), None)
        emitted = emit_memory_candidate(_candidate())

        self.assertFalse(retrieval.provider_available)
        self.assertEqual(retrieval.evidence, ())
        self.assertEqual(emitted.candidate_id.value, "candidate_database_choice")


if __name__ == "__main__":
    unittest.main()
