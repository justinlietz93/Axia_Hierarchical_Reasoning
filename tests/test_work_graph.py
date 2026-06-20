from __future__ import annotations

import unittest

from axia.formation import (
    RefinementCycle,
    ScorePolicy,
    TaskConstitutionFailure,
    WorkGraphFailure,
    WorkNode,
    build_task_constitution,
    form_work_graph,
)
from axia.formation.canonical_request import CanonicalRequest
from axia.shared.ids import NodeId


def _constitution():
    return build_task_constitution(
        CanonicalRequest(
            source_request_hash="request-hash",
            intent="compare database options",
            deliverable_type="technical recommendation",
            constraints=("local-first",),
            unknowns=(),
            risk_flags=(),
            output_format="concise recommendation",
            expected_depth="standard",
            needed_context=(),
        )
    )


def _node(name: str, kind: str, depends_on: tuple[str, ...] = (), retry_limit: int = 2) -> WorkNode:
    return WorkNode(
        node_id=NodeId.from_value(f"node_{name}"),
        kind=kind,
        depends_on=tuple(NodeId.from_value(f"node_{dependency}") for dependency in depends_on),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        context_scope=("constitution",),
        retry_limit=retry_limit,
        score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65),
        failure_behavior="retry",
    )


class WorkGraphTests(unittest.TestCase):
    def test_orders_nodes_from_explicit_dependencies(self) -> None:
        graph = form_work_graph(
            _constitution(),
            (
                _node("canonicalize", "canonicalize"),
                _node("constitute", "constitute", ("canonicalize",)),
                _node("draft", "draft", ("constitute",)),
            ),
        )

        self.assertEqual(
            [node.node_id.value for node in graph.topological_order()],
            ["node_canonicalize", "node_constitute", "node_draft"],
        )
        self.assertEqual(
            [(edge.source_node_id.value, edge.target_node_id.value) for edge in graph.edges],
            [("node_canonicalize", "node_constitute"), ("node_constitute", "node_draft")],
        )

    def test_allows_only_bounded_refinement_cycles_from_repair(self) -> None:
        graph = form_work_graph(
            _constitution(),
            (
                _node("draft", "draft"),
                _node("critique", "critique", ("draft",)),
                _node("repair", "repair", ("critique",), retry_limit=2),
            ),
            (
                RefinementCycle(
                    from_node_id=NodeId.from_value("node_repair"),
                    to_node_id=NodeId.from_value("node_critique"),
                    max_iterations=2,
                ),
            ),
        )

        self.assertEqual(len(graph.refinement_cycles), 1)
        self.assertEqual([node.node_id.value for node in graph.topological_order()], ["node_draft", "node_critique", "node_repair"])

    def test_rejects_ordinary_dependency_cycles(self) -> None:
        with self.assertRaises(WorkGraphFailure) as failure:
            form_work_graph(
                _constitution(),
                (
                    _node("draft", "draft", ("critique",)),
                    _node("critique", "critique", ("draft",)),
                ),
            )

        self.assertEqual(failure.exception.kind, "work_graph_dependency_cycle")

    def test_rejects_unbounded_or_nonrepair_refinement_cycles(self) -> None:
        with self.assertRaises(WorkGraphFailure) as unbounded_failure:
            RefinementCycle(
                from_node_id=NodeId.from_value("node_repair"),
                to_node_id=NodeId.from_value("node_critique"),
                max_iterations=0,
            )

        with self.assertRaises(WorkGraphFailure) as source_failure:
            form_work_graph(
                _constitution(),
                (_node("draft", "draft"), _node("critique", "critique", ("draft",))),
                (
                    RefinementCycle(
                        from_node_id=NodeId.from_value("node_critique"),
                        to_node_id=NodeId.from_value("node_draft"),
                        max_iterations=1,
                    ),
                ),
            )

        self.assertEqual(unbounded_failure.exception.kind, "work_graph_unbounded_refinement")
        self.assertEqual(source_failure.exception.kind, "work_graph_invalid_refinement_source")

    def test_requires_a_task_constitution_before_graph_formation(self) -> None:
        with self.assertRaises(TaskConstitutionFailure) as failure:
            form_work_graph(None, (_node("draft", "draft"),))

        self.assertEqual(failure.exception.kind, "task_constitution_required")


if __name__ == "__main__":
    unittest.main()
