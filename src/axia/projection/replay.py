from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.formation.structured_output import validate_json_schema
from axia.projection.run_manifest import RUN_MANIFEST_SCHEMA
from axia.shared.errors import AxiaError
from axia.shared.ids import stable_json_hash


@dataclass(frozen=True)
class ReplayNodeDecision:
    """A controller decision reproduced from one saved node result and node contract."""

    node_id: str
    attempt: int
    status: str
    validation_accepted: bool
    score_decision: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "attempt": self.attempt,
            "status": self.status,
            "validation_accepted": self.validation_accepted,
            "score_decision": self.score_decision,
        }


@dataclass(frozen=True)
class ReplayResult:
    """The deterministic controller state reconstructed without invoking a model provider."""

    run_id: str
    graph_order: tuple[str, ...]
    node_decisions: tuple[ReplayNodeDecision, ...]
    final_answer: str
    final_source_artifact_ids: tuple[str, ...]
    prompt_hashes: Mapping[str, str]

    def to_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "graph_order": list(self.graph_order),
            "node_decisions": [decision.to_payload() for decision in self.node_decisions],
            "final_answer": self.final_answer,
            "final_source_artifact_ids": list(self.final_source_artifact_ids),
            "prompt_hashes": dict(sorted(self.prompt_hashes.items())),
        }


@dataclass(frozen=True)
class ReplayFailure(AxiaError):
    """A deterministic failure while reproducing controller state from saved evidence."""


def replay_manifest_payload(payload: Mapping[str, object]) -> ReplayResult:
    """Reproduce graph order and controller decisions from one saved manifest payload only."""

    issues = validate_json_schema(payload, RUN_MANIFEST_SCHEMA)
    if issues:
        issue = issues[0]
        raise ReplayFailure(kind="replay_manifest_schema_invalid", message=f"{issue.path} {issue.message}")
    run_id = _required_string(payload.get("run_id"), "replay_manifest_schema_invalid")
    prompt_hashes = _string_mapping(payload.get("prompt_hashes"), "replay_prompt_hashes_invalid")
    work_graph = _mapping(payload.get("work_graph"), "replay_work_graph_invalid")
    nodes = _object_list(work_graph.get("nodes"), "replay_work_graph_invalid")
    graph_order = _topological_order(nodes)
    node_policies = {
        _required_string(node.get("node_id"), "replay_work_graph_invalid"): _mapping(
            node.get("score_policy"), "replay_score_policy_invalid"
        )
        for node in nodes
    }
    graph_node_ids = set(node_policies)
    node_results = _object_list(payload.get("node_results"), "replay_node_results_invalid")
    result_keys: set[tuple[str, int]] = set()
    decisions: list[ReplayNodeDecision] = []
    for result in node_results:
        decision = _replay_node_result(result, run_id, graph_node_ids, node_policies, prompt_hashes)
        key = (decision.node_id, decision.attempt)
        if key in result_keys:
            raise ReplayFailure(kind="replay_duplicate_node_result", message="saved replay data repeats a node attempt")
        result_keys.add(key)
        decisions.append(decision)
    final_answer, final_source_artifact_ids = _replay_final_answer(payload.get("final_answer"), node_results)
    return ReplayResult(
        run_id=run_id,
        graph_order=graph_order,
        node_decisions=tuple(decisions),
        final_answer=final_answer,
        final_source_artifact_ids=final_source_artifact_ids,
        prompt_hashes=prompt_hashes,
    )


def _replay_node_result(
    result: Mapping[str, object],
    run_id: str,
    graph_node_ids: set[str],
    node_policies: Mapping[str, Mapping[str, object]],
    prompt_hashes: Mapping[str, str],
) -> ReplayNodeDecision:
    node_id = _required_string(result.get("node_id"), "replay_node_result_invalid")
    attempt = _positive_integer(result.get("attempt"), "replay_node_result_invalid")
    status = _required_string(result.get("status"), "replay_node_result_invalid")
    prompt_hash = _required_string(result.get("prompt_hash"), "replay_node_result_invalid")
    if node_id not in graph_node_ids:
        raise ReplayFailure(kind="replay_unknown_node", message="saved node result does not belong to the saved graph")
    expected_prompt_key = f"{node_id}:attempt:{attempt}"
    if prompt_hashes.get(expected_prompt_key) != prompt_hash:
        raise ReplayFailure(kind="replay_prompt_hash_mismatch", message="saved node prompt hash does not match manifest prompt hashes")
    validation_errors = _list(result.get("validation_errors"), "replay_node_result_invalid")
    artifact_present = result.get("artifact") is not None
    validation_accepted = artifact_present and not validation_errors
    scorecard = result.get("scorecard")
    score_decision = None
    if scorecard is not None:
        scorecard_payload = _mapping(scorecard, "replay_scorecard_invalid")
        _validate_scorecard_lineage(scorecard_payload, run_id, node_id, result.get("artifact_id"))
        score_decision = _replay_score_decision(scorecard_payload, node_policies[node_id])
    if status in {"accepted", "repaired"} and (not validation_accepted or score_decision != "accept"):
        raise ReplayFailure(
            kind="replay_accepted_result_invalid",
            message="accepted or repaired node results require validation and an accepting scorecard decision",
        )
    _validate_provider_response(result.get("provider_response"))
    return ReplayNodeDecision(
        node_id=node_id,
        attempt=attempt,
        status=status,
        validation_accepted=validation_accepted,
        score_decision=score_decision,
    )


def _topological_order(nodes: tuple[Mapping[str, object], ...]) -> tuple[str, ...]:
    node_ids: list[str] = []
    dependencies: dict[str, set[str]] = {}
    for node in nodes:
        node_id = _required_string(node.get("node_id"), "replay_work_graph_invalid")
        if node_id in dependencies:
            raise ReplayFailure(kind="replay_duplicate_graph_node", message="saved graph contains duplicate node IDs")
        node_ids.append(node_id)
        dependencies[node_id] = set(_string_list(node.get("depends_on"), "replay_work_graph_invalid"))
    if any(not values.issubset(set(node_ids)) for values in dependencies.values()):
        raise ReplayFailure(kind="replay_unknown_dependency", message="saved graph contains an unknown dependency")
    ordered: list[str] = []
    pending = {node_id: set(values) for node_id, values in dependencies.items()}
    ready = [node_id for node_id in node_ids if not pending[node_id]]
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for candidate in node_ids:
            if node_id in pending[candidate]:
                pending[candidate].remove(node_id)
                if not pending[candidate] and candidate not in ordered and candidate not in ready:
                    ready.append(candidate)
    if len(ordered) != len(node_ids):
        raise ReplayFailure(kind="replay_graph_cycle", message="saved graph dependencies are cyclic")
    return tuple(ordered)


def _replay_score_decision(scorecard: Mapping[str, object], policy: Mapping[str, object]) -> str:
    dimensions = _object_list(scorecard.get("dimensions"), "replay_scorecard_invalid")
    if not dimensions:
        raise ReplayFailure(kind="replay_scorecard_invalid", message="saved scorecard requires dimensions")
    scores = [_score_value(dimension.get("score")) for dimension in dimensions]
    accept = _score_value(policy.get("accept_threshold"))
    repair = _score_value(policy.get("repair_threshold"))
    regenerate = _score_value(policy.get("regenerate_threshold"))
    lowest = min(scores)
    expected = "accept" if lowest >= accept else "repair" if lowest >= repair else "regenerate" if lowest >= regenerate else "ask_user"
    declared = _required_string(scorecard.get("decision"), "replay_scorecard_invalid")
    if declared != expected:
        raise ReplayFailure(kind="replay_score_decision_mismatch", message="saved scorecard decision does not match saved node score policy")
    return expected


def _validate_scorecard_lineage(scorecard: Mapping[str, object], run_id: str, node_id: str, artifact_id: object) -> None:
    if _required_string(scorecard.get("source_run_id"), "replay_scorecard_invalid") != run_id:
        raise ReplayFailure(kind="replay_scorecard_lineage_mismatch", message="saved scorecard belongs to another run")
    if _required_string(scorecard.get("source_node_id"), "replay_scorecard_invalid") != node_id:
        raise ReplayFailure(kind="replay_scorecard_lineage_mismatch", message="saved scorecard belongs to another node")
    if not isinstance(artifact_id, str) or _required_string(scorecard.get("source_artifact_id"), "replay_scorecard_invalid") != artifact_id:
        raise ReplayFailure(kind="replay_scorecard_lineage_mismatch", message="saved scorecard belongs to another artifact")


def _replay_final_answer(value: object, node_results: tuple[Mapping[str, object], ...]) -> tuple[str, tuple[str, ...]]:
    accepted_artifact_ids = {
        artifact_id
        for result in node_results
        if result.get("status") in {"accepted", "repaired"} and isinstance((artifact_id := result.get("artifact_id")), str)
    }
    if isinstance(value, str):
        if not value.strip():
            raise ReplayFailure(kind="replay_final_answer_invalid", message="saved final answer must be non-empty")
        return value, ()
    final_payload = _mapping(value, "replay_final_answer_invalid")
    rendered_answer = _required_string(final_payload.get("rendered_answer"), "replay_final_answer_invalid")
    claims = _object_list(final_payload.get("claims"), "replay_final_answer_invalid")
    source_ids = tuple(_required_string(claim.get("source_artifact_id"), "replay_final_answer_invalid") for claim in claims)
    if not source_ids or not set(source_ids).issubset(accepted_artifact_ids):
        raise ReplayFailure(kind="replay_final_artifact_mismatch", message="saved final answer must cite accepted manifest artifacts")
    return rendered_answer, source_ids


def _validate_provider_response(value: object) -> None:
    if value is None:
        return
    response = _mapping(value, "replay_provider_response_invalid")
    text = _required_string(response.get("text"), "replay_provider_response_invalid")
    metadata = _string_mapping(response.get("metadata"), "replay_provider_response_invalid")
    content_hash = _required_string(response.get("content_hash"), "replay_provider_response_invalid")
    if content_hash != stable_json_hash({"text": text, "metadata": dict(metadata)}):
        raise ReplayFailure(kind="replay_provider_response_hash_mismatch", message="saved provider response hash is inconsistent")


def _mapping(value: object, kind: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReplayFailure(kind=kind, message="saved replay evidence must be an object")
    return value


def _object_list(value: object, kind: str) -> tuple[Mapping[str, object], ...]:
    return tuple(_mapping(item, kind) for item in _list(value, kind))


def _list(value: object, kind: str) -> list[object]:
    if not isinstance(value, list):
        raise ReplayFailure(kind=kind, message="saved replay evidence must be an array")
    return value


def _string_list(value: object, kind: str) -> tuple[str, ...]:
    return tuple(_required_string(item, kind) for item in _list(value, kind))


def _string_mapping(value: object, kind: str) -> Mapping[str, str]:
    mapping = _mapping(value, kind)
    result: dict[str, str] = {}
    for key, item in mapping.items():
        result[_required_string(key, kind)] = _required_string(item, kind)
    return result


def _required_string(value: object, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplayFailure(kind=kind, message="saved replay strings must be non-empty")
    return value


def _positive_integer(value: object, kind: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ReplayFailure(kind=kind, message="saved replay attempts must be positive integers")
    return value


def _score_value(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
        raise ReplayFailure(kind="replay_scorecard_invalid", message="saved score values must be within [0, 1]")
    return float(value)
