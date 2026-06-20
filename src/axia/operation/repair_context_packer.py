from __future__ import annotations

from axia.formation.context_pack import ContextPack, ContextReference, build_context_pack
from axia.formation.repair import REPAIR_CONTEXT_SCOPES, RepairContext, RepairFailure
from axia.formation.task_constitution import TaskConstitution
from axia.formation.work_graph import WorkNode


def pack_repair_context(
    repair_node: WorkNode,
    repair_context: RepairContext,
    constitution: TaskConstitution,
    *,
    node_instruction: str,
) -> ContextPack:
    """Translate one admitted repair context into the exact scoped micro-agent input."""

    if repair_node.kind != "repair":
        raise RepairFailure(
            kind="repair_node_kind_invalid",
            message="only a repair node may receive a repair context pack",
        )
    if set(repair_node.context_scope) != set(REPAIR_CONTEXT_SCOPES):
        raise RepairFailure(
            kind="repair_context_scope_invalid",
            message="repair nodes must declare failed artifact, scorecard, evidence, and target scopes only",
        )

    failed_artifact = ContextReference.from_content(
        scope="failed_artifact",
        source_type="artifact",
        reference_id=repair_context.source_artifact_id.value,
        content={
            "artifact_id": repair_context.source_artifact_id.value,
            "payload": repair_context.failed_artifact_payload,
            "rendered_output": repair_context.failed_rendered_output,
            "validation_errors": list(repair_context.validation_errors),
        },
        accepted=False,
    )
    scorecard = ContextReference.from_content(
        scope="scorecard",
        source_type="scorecard",
        reference_id=repair_context.scorecard.scorecard_id.value,
        content=repair_context.scorecard.to_payload(),
    )
    repair_target = ContextReference.from_content(
        scope="repair_target",
        source_type="policy",
        reference_id=f"policy_{repair_context.source_node_id.value}",
        content={
            "target_threshold": repair_context.target_threshold,
            "failed_dimensions": [dimension.to_payload() for dimension in repair_context.failed_dimensions],
        },
    )
    evidence = tuple(
        ContextReference.from_content(
            scope="relevant_evidence",
            source_type="evidence",
            reference_id=reference.reference_id,
            content=reference.content,
            accepted=reference.accepted,
        )
        for reference in repair_context.relevant_evidence
    )
    return build_context_pack(
        repair_node,
        node_instruction=node_instruction,
        constitution=constitution,
        prior_artifacts=(failed_artifact, scorecard, repair_target),
        context_records=evidence,
    )
