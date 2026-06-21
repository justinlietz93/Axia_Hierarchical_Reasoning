from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.formation.task_constitution import TaskConstitution, require_task_constitution
from axia.shared.errors import AxiaError
from axia.shared.ids import NodeId


WORK_NODE_KINDS = frozenset(
    {
        "canonicalize",
        "constitute",
        "retrieve",
        "plan",
        "decompose",
        "assemble_context",
        "analyze",
        "draft",
        "critique",
        "repair",
        "merge",
        "verify",
        "finalize",
        "final",
        "synthesize",
        "emit_memory_candidate",
    }
)
FAILURE_BEHAVIORS = frozenset({"fail_run", "retry", "continue_with_caveat"})

CANONICALIZE_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intent",
        "deliverable_type",
        "constraints",
        "unknowns",
        "risk_flags",
        "output_format",
        "expected_depth",
        "needed_context",
    ],
    "properties": {
        "intent": {"type": "string", "minLength": 1},
        "deliverable_type": {"type": "string", "minLength": 1},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "output_format": {"type": "string", "minLength": 1},
        "expected_depth": {"type": "string", "enum": ["brief", "standard", "deep"]},
        "needed_context": {"type": "array", "items": {"type": "string"}},
    },
}
CONSTITUTION_OUTPUT_SCHEMA: Mapping[str, object] = {"type": "object"}
RETRIEVAL_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["task_mission", "evidence", "caveats"],
    "properties": {
        "task_mission": {"type": "string", "minLength": 1},
        "evidence": {"type": "array"},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
}
PLAN_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["task_mission", "steps", "assumptions", "unresolved_questions", "addressed_constraints"],
    "properties": {
        "task_mission": {"type": "string", "minLength": 1},
        "steps": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "assumptions": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "unresolved_questions": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "addressed_constraints": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}
ANSWER_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {
        "answer": {"type": "string", "minLength": 1},
    },
}
CRITIQUE_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["task_mission", "strengths", "gaps", "repair_focus", "addressed_constraints"],
    "properties": {
        "task_mission": {"type": "string", "minLength": 1},
        "strengths": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "gaps": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "repair_focus": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "addressed_constraints": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}
FINAL_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["task_mission", "answer", "source_artifact_id"],
    "properties": {
        "task_mission": {"type": "string", "minLength": 1},
        "answer": {"type": "string", "minLength": 1},
        "source_artifact_id": {"type": "string", "minLength": 1},
    },
}
MEMORY_CANDIDATE_OUTPUT_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["task_mission", "emitted", "reason"],
    "properties": {
        "task_mission": {"type": "string", "minLength": 1},
        "emitted": {"type": "boolean"},
        "reason": {"type": "string", "minLength": 1},
    },
}


@dataclass(frozen=True)
class ScorePolicy:
    """Per-node acceptance, repair, regeneration, and clarification thresholds."""

    accept_threshold: float
    repair_threshold: float
    regenerate_threshold: float = 0.45

    def __post_init__(self) -> None:
        if not 0 <= self.regenerate_threshold <= self.repair_threshold <= self.accept_threshold <= 1:
            raise WorkGraphFailure(
                kind="work_graph_invalid_score_policy",
                message="score thresholds must satisfy 0 <= regenerate <= repair <= accept <= 1",
            )

    def decision_for(self, lowest_dimension_score: float) -> str:
        """Choose the only next action permitted by this node's score policy."""

        if not 0 <= lowest_dimension_score <= 1:
            raise WorkGraphFailure(
                kind="work_graph_invalid_score",
                message="score policy decisions require a score within [0, 1]",
            )
        if lowest_dimension_score >= self.accept_threshold:
            return "accept"
        if lowest_dimension_score >= self.repair_threshold:
            return "repair"
        if lowest_dimension_score >= self.regenerate_threshold:
            return "regenerate"
        return "ask_user"

    def to_payload(self) -> dict[str, float]:
        return {
            "accept_threshold": self.accept_threshold,
            "repair_threshold": self.repair_threshold,
            "regenerate_threshold": self.regenerate_threshold,
        }


@dataclass(frozen=True)
class WorkNode:
    """A narrow reasoning step with its complete execution contract."""

    node_id: NodeId
    kind: str
    depends_on: tuple[NodeId, ...]
    input_schema: Mapping[str, object]
    output_schema: Mapping[str, object]
    context_scope: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    retry_limit: int
    score_policy: ScorePolicy
    failure_behavior: str

    def __post_init__(self) -> None:
        if self.kind not in WORK_NODE_KINDS:
            raise WorkGraphFailure(
                kind="work_graph_unknown_node_kind",
                message=f"unsupported node kind {self.kind!r}",
            )
        if not self.input_schema or not self.output_schema:
            raise WorkGraphFailure(
                kind="work_graph_missing_schema",
                message=f"node {self.node_id} requires input and output schemas",
            )
        if not self.context_scope:
            raise WorkGraphFailure(
                kind="work_graph_missing_context_scope",
                message=f"node {self.node_id} requires an explicit context scope",
            )
        if any(not operation.strip() for operation in self.allowed_operations):
            raise WorkGraphFailure(
                kind="work_graph_invalid_allowed_operations",
                message=f"node {self.node_id} has a blank allowed operation",
            )
        if len(set(self.allowed_operations)) != len(self.allowed_operations):
            raise WorkGraphFailure(
                kind="work_graph_invalid_allowed_operations",
                message=f"node {self.node_id} repeats an allowed operation",
            )
        if self.retry_limit < 0:
            raise WorkGraphFailure(
                kind="work_graph_invalid_retry_limit",
                message=f"node {self.node_id} retry_limit must not be negative",
            )
        if self.failure_behavior not in FAILURE_BEHAVIORS:
            raise WorkGraphFailure(
                kind="work_graph_invalid_failure_behavior",
                message=f"node {self.node_id} has unsupported failure behavior {self.failure_behavior!r}",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id.value,
            "kind": self.kind,
            "depends_on": [node_id.value for node_id in self.depends_on],
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "context_scope": list(self.context_scope),
            "allowed_operations": list(self.allowed_operations),
            "retry_limit": self.retry_limit,
            "score_policy": self.score_policy.to_payload(),
            "failure_behavior": self.failure_behavior,
        }


@dataclass(frozen=True)
class WorkEdge:
    """A directed dependency edge derived from one node contract."""

    source_node_id: NodeId
    target_node_id: NodeId


@dataclass(frozen=True)
class RefinementCycle:
    """An explicit, bounded transition from repair back to a prior reasoning step."""

    from_node_id: NodeId
    to_node_id: NodeId
    max_iterations: int

    def __post_init__(self) -> None:
        if self.max_iterations <= 0:
            raise WorkGraphFailure(
                kind="work_graph_unbounded_refinement",
                message="refinement cycles require a positive max_iterations",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "from_node_id": self.from_node_id.value,
            "to_node_id": self.to_node_id.value,
            "max_iterations": self.max_iterations,
        }


@dataclass(frozen=True)
class WorkGraph:
    """A constitution-derived, replayable graph with bounded refinement only."""

    constitution_revision_hash: str
    nodes: tuple[WorkNode, ...]
    refinement_cycles: tuple[RefinementCycle, ...] = ()

    def __post_init__(self) -> None:
        if not self.constitution_revision_hash:
            raise WorkGraphFailure(
                kind="work_graph_missing_constitution",
                message="a work graph requires a task constitution revision hash",
            )
        if not self.nodes:
            raise WorkGraphFailure(kind="work_graph_empty", message="a work graph requires at least one node")

        node_map = self._node_map()
        for node in self.nodes:
            for dependency in node.depends_on:
                if dependency not in node_map:
                    raise WorkGraphFailure(
                        kind="work_graph_unknown_dependency",
                        message=f"node {node.node_id} depends on unknown node {dependency}",
                    )
                if dependency == node.node_id:
                    raise WorkGraphFailure(
                        kind="work_graph_dependency_cycle",
                        message=f"node {node.node_id} cannot depend on itself",
                    )

        self._topological_node_ids(node_map)
        for cycle in self.refinement_cycles:
            self._validate_refinement_cycle(cycle, node_map)

    @property
    def edges(self) -> tuple[WorkEdge, ...]:
        return tuple(
            WorkEdge(source_node_id=dependency, target_node_id=node.node_id)
            for node in self.nodes
            for dependency in node.depends_on
        )

    def topological_order(self) -> tuple[WorkNode, ...]:
        node_map = self._node_map()
        return tuple(node_map[node_id] for node_id in self._topological_node_ids(node_map))

    def to_payload(self) -> dict[str, object]:
        return {
            "constitution_revision_hash": self.constitution_revision_hash,
            "nodes": [node.to_payload() for node in self.nodes],
            "refinement_cycles": [cycle.to_payload() for cycle in self.refinement_cycles],
        }

    def _node_map(self) -> dict[NodeId, WorkNode]:
        node_map = {node.node_id: node for node in self.nodes}
        if len(node_map) != len(self.nodes):
            raise WorkGraphFailure(
                kind="work_graph_duplicate_node",
                message="work graph node IDs must be unique",
            )
        return node_map

    def _topological_node_ids(self, node_map: Mapping[NodeId, WorkNode]) -> tuple[NodeId, ...]:
        pending_dependencies = {node_id: set(node.depends_on) for node_id, node in node_map.items()}
        ordered: list[NodeId] = []
        ready = [node.node_id for node in self.nodes if not pending_dependencies[node.node_id]]

        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for candidate in self.nodes:
                dependencies = pending_dependencies[candidate.node_id]
                if node_id in dependencies:
                    dependencies.remove(node_id)
                    if not dependencies and candidate.node_id not in ordered and candidate.node_id not in ready:
                        ready.append(candidate.node_id)

        if len(ordered) != len(node_map):
            raise WorkGraphFailure(
                kind="work_graph_dependency_cycle",
                message="ordinary work graph dependencies must be acyclic",
            )
        return tuple(ordered)

    def _validate_refinement_cycle(
        self,
        cycle: RefinementCycle,
        node_map: Mapping[NodeId, WorkNode],
    ) -> None:
        source = node_map.get(cycle.from_node_id)
        target = node_map.get(cycle.to_node_id)
        if source is None or target is None:
            raise WorkGraphFailure(
                kind="work_graph_unknown_refinement_node",
                message="refinement cycles must reference existing nodes",
            )
        if source.kind != "repair":
            raise WorkGraphFailure(
                kind="work_graph_invalid_refinement_source",
                message="only repair nodes may start refinement cycles",
            )
        if cycle.max_iterations > source.retry_limit:
            raise WorkGraphFailure(
                kind="work_graph_unbounded_refinement",
                message="refinement cycle iterations must not exceed the repair node retry limit",
            )


@dataclass(frozen=True)
class WorkGraphFailure(AxiaError):
    """A deterministic work-graph formation failure."""


def form_work_graph(
    constitution: TaskConstitution | None,
    nodes: tuple[WorkNode, ...],
    refinement_cycles: tuple[RefinementCycle, ...] = (),
) -> WorkGraph:
    """Form a graph only from an admitted immutable task constitution."""

    admitted_constitution = require_task_constitution(constitution)
    permitted_operations = set(admitted_constitution.allowed_operations) - {"none"}
    for node in nodes:
        unpermitted_operations = set(node.allowed_operations) - permitted_operations
        if unpermitted_operations:
            raise WorkGraphFailure(
                kind="work_graph_unpermitted_operation",
                message=(
                    f"node {node.node_id} requests operations not admitted by the constitution: "
                    f"{', '.join(sorted(unpermitted_operations))}"
                ),
            )
    return WorkGraph(
        constitution_revision_hash=admitted_constitution.revision_hash(),
        nodes=nodes,
        refinement_cycles=refinement_cycles,
    )


def build_standard_work_graph(constitution: TaskConstitution | None) -> WorkGraph:
    """Build the fixed, narrow standard reasoning graph from one constitution."""

    admitted_constitution = require_task_constitution(constitution)
    nodes = (
        _standard_node("canonicalize", "canonicalize", (), ("source_request",), (), 1, "retry", CANONICALIZE_OUTPUT_SCHEMA),
        _standard_node("constitute", "constitute", ("canonicalize",), ("canonical_request",), (), 0, "fail_run", CONSTITUTION_OUTPUT_SCHEMA),
        _standard_node(
            "retrieve",
            "retrieve",
            ("constitute",),
            ("constitution",),
            tuple(operation for operation in admitted_constitution.allowed_operations if operation != "none"),
            0,
            "continue_with_caveat",
            RETRIEVAL_OUTPUT_SCHEMA,
        ),
        _standard_node("plan", "plan", ("constitute", "retrieve"), ("constitution", "retrieved_evidence"), (), 1, "retry", PLAN_OUTPUT_SCHEMA),
        _standard_node("draft", "draft", ("plan",), ("plan",), (), 1, "retry", ANSWER_OUTPUT_SCHEMA),
        _standard_node("critique", "critique", ("draft", "constitute"), ("draft", "constitution"), (), 1, "retry", CRITIQUE_OUTPUT_SCHEMA),
        _standard_node(
            "repair",
            "repair",
            ("draft", "critique"),
            ("failed_artifact", "scorecard", "relevant_evidence", "repair_target"),
            (),
            admitted_constitution.limits.max_retries_per_node,
            "retry",
            ANSWER_OUTPUT_SCHEMA,
        ),
        _standard_node("verify", "verify", ("repair", "constitute", "retrieve"), ("repaired_draft", "constitution", "retrieved_evidence"), (), 0, "fail_run", ANSWER_OUTPUT_SCHEMA),
        _standard_node(
            "final",
            "final",
            ("repair", "verify"),
            ("constitution", "accepted_artifacts", "scorecards", "unresolved_caveats", "requested_format", "style_constraints"),
            (),
            0,
            "fail_run",
            FINAL_OUTPUT_SCHEMA,
        ),
        _standard_node("memory_candidates", "emit_memory_candidate", ("final",), ("final_answer",), (), 0, "continue_with_caveat", MEMORY_CANDIDATE_OUTPUT_SCHEMA),
    )
    return form_work_graph(
        admitted_constitution,
        nodes,
        refinement_cycles=(
            RefinementCycle(
                from_node_id=NodeId.from_value("node_repair"),
                to_node_id=NodeId.from_value("node_critique"),
                max_iterations=admitted_constitution.limits.max_retries_per_node,
            ),
        ),
    )


def _standard_node(
    name: str,
    kind: str,
    dependencies: tuple[str, ...],
    context_scope: tuple[str, ...],
    allowed_operations: tuple[str, ...],
    retry_limit: int,
    failure_behavior: str,
    output_schema: Mapping[str, object],
) -> WorkNode:
    return WorkNode(
        node_id=NodeId.from_value(f"node_{name}"),
        kind=kind,
        depends_on=tuple(NodeId.from_value(f"node_{dependency}") for dependency in dependencies),
        input_schema={"type": "object", "required": list(context_scope)},
        output_schema=output_schema,
        context_scope=context_scope,
        allowed_operations=allowed_operations,
        retry_limit=retry_limit,
        score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65),
        failure_behavior=failure_behavior,
    )
