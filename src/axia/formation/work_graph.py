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
        "decompose",
        "assemble_context",
        "analyze",
        "draft",
        "critique",
        "repair",
        "merge",
        "verify",
        "finalize",
        "synthesize",
        "emit_memory_candidate",
    }
)
FAILURE_BEHAVIORS = frozenset({"fail_run", "retry", "continue_with_caveat"})


@dataclass(frozen=True)
class ScorePolicy:
    """Per-node acceptance and repair thresholds."""

    accept_threshold: float
    repair_threshold: float

    def __post_init__(self) -> None:
        if not 0 < self.repair_threshold <= self.accept_threshold <= 1:
            raise WorkGraphFailure(
                kind="work_graph_invalid_score_policy",
                message="score thresholds must satisfy 0 < repair <= accept <= 1",
            )


@dataclass(frozen=True)
class WorkNode:
    """A narrow reasoning step with its complete execution contract."""

    node_id: NodeId
    kind: str
    depends_on: tuple[NodeId, ...]
    input_schema: Mapping[str, object]
    output_schema: Mapping[str, object]
    context_scope: tuple[str, ...]
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
    return WorkGraph(
        constitution_revision_hash=admitted_constitution.revision_hash(),
        nodes=nodes,
        refinement_cycles=refinement_cycles,
    )
