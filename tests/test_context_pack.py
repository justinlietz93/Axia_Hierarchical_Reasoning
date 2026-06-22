from __future__ import annotations

import unittest

from axia.formation import (
    CONTEXT_BUDGETS_BY_NODE_KIND,
    ContextPackFailure,
    ContextReference,
    ScorePolicy,
    WorkNode,
    build_context_pack,
    build_task_constitution,
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
            needed_context=("project architecture",),
        )
    )


def _node() -> WorkNode:
    return WorkNode(
        node_id=NodeId.from_value("node_verify"),
        kind="verify",
        depends_on=(),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        context_scope=("constitution", "repaired_draft", "retrieved_evidence"),
        allowed_operations=(),
        retry_limit=0,
        score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65),
        failure_behavior="fail_run",
    )


class ContextPackTests(unittest.TestCase):
    def test_forms_a_stable_scope_bounded_pack(self) -> None:
        node = _node()
        repaired_draft = ContextReference.from_content(
            scope="repaired_draft",
            source_type="artifact",
            reference_id="artifact_repaired_draft",
            content={"outline": ["compare options"]},
        )
        evidence_b = ContextReference.from_content(
            scope="retrieved_evidence",
            source_type="evidence",
            reference_id="evidence_b",
            content="B",
        )
        evidence_a = ContextReference.from_content(
            scope="retrieved_evidence",
            source_type="evidence",
            reference_id="evidence_a",
            content="A",
        )

        first = build_context_pack(
            node,
            node_instruction="Verify the comparison.",
            constitution=_constitution(),
            prior_artifacts=(repaired_draft,),
            context_records=(evidence_b, evidence_a),
        )
        second = build_context_pack(
            node,
            node_instruction="Verify the comparison.",
            constitution=_constitution(),
            prior_artifacts=(repaired_draft,),
            context_records=(evidence_a, evidence_b),
        )

        self.assertEqual(first, second)
        self.assertEqual(
            [reference.reference_id for reference in first.references],
            ["artifact_repaired_draft", "evidence_a", "evidence_b"],
        )
        self.assertEqual(first.prompt_inputs()["retrieved_evidence"], ["A", "B"])
        self.assertIn("mission", first.constitution_subset)
        self.assertEqual(first.max_serialized_characters, CONTEXT_BUDGETS_BY_NODE_KIND["verify"])

    def test_rejects_unscoped_rejected_or_over_budget_material(self) -> None:
        node = _node()
        with self.assertRaises(ContextPackFailure) as scope_failure:
            build_context_pack(
                node,
                node_instruction="Verify the comparison.",
                constitution=_constitution(),
                prior_artifacts=(
                    ContextReference.from_content(
                        scope="full_run_log",
                        source_type="artifact",
                        reference_id="artifact_log",
                        content="not admitted",
                    ),
                ),
                context_records=(
                    ContextReference.from_content(
                        scope="retrieved_evidence",
                        source_type="evidence",
                        reference_id="evidence_a",
                        content="A",
                    ),
                ),
            )

        with self.assertRaises(ContextPackFailure) as rejected_failure:
            build_context_pack(
                node,
                node_instruction="Verify the comparison.",
                constitution=_constitution(),
                prior_artifacts=(
                    ContextReference.from_content(
                        scope="repaired_draft",
                        source_type="artifact",
                        reference_id="artifact_rejected",
                        content="rejected draft",
                        accepted=False,
                    ),
                ),
                context_records=(
                    ContextReference.from_content(
                        scope="retrieved_evidence",
                        source_type="evidence",
                        reference_id="evidence_a",
                        content="A",
                    ),
                ),
            )

        with self.assertRaises(ContextPackFailure) as budget_failure:
            build_context_pack(
                node,
                node_instruction="Verify the comparison.",
                constitution=_constitution(),
                prior_artifacts=(
                    ContextReference.from_content(
                        scope="repaired_draft",
                        source_type="artifact",
                        reference_id="artifact_repaired_draft",
                        content="plan",
                    ),
                ),
                context_records=(
                    ContextReference.from_content(
                        scope="retrieved_evidence",
                        source_type="evidence",
                        reference_id="evidence_a",
                        content="A",
                    ),
                ),
                max_serialized_characters=1,
            )

        self.assertEqual(scope_failure.exception.kind, "context_pack_scope_violation")
        self.assertEqual(rejected_failure.exception.kind, "context_pack_rejected_artifact")
        self.assertEqual(budget_failure.exception.kind, "context_pack_budget_exceeded")

    def test_rejects_reference_that_attempts_to_replace_the_constitution_subset(self) -> None:
        with self.assertRaises(ContextPackFailure) as failure:
            build_context_pack(
                _node(),
                node_instruction="Verify the comparison.",
                constitution=_constitution(),
                prior_artifacts=(
                    ContextReference.from_content(
                        scope="constitution",
                        source_type="artifact",
                        reference_id="artifact_override",
                        content={"allowed_operations": ["shell"]},
                    ),
                    ContextReference.from_content(
                        scope="repaired_draft",
                        source_type="artifact",
                        reference_id="artifact_repaired_draft",
                        content="draft",
                    ),
                ),
                context_records=(
                    ContextReference.from_content(
                        scope="retrieved_evidence",
                        source_type="evidence",
                        reference_id="evidence_a",
                        content="A",
                    ),
                ),
            )

        self.assertEqual(failure.exception.kind, "context_pack_scope_violation")


if __name__ == "__main__":
    unittest.main()
