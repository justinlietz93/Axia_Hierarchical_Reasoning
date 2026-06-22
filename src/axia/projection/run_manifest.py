from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from axia.formation.canonical_request import CanonicalRequest
from axia.formation.final_answer import FinalAnswer
from axia.formation.memory_candidate import MemoryCandidate
from axia.formation.micro_agent import TypedArtifact
from axia.formation.scorecard import Scorecard
from axia.formation.structured_output import ValidationIssue
from axia.formation.task_constitution import TaskConstitution
from axia.formation.work_graph import WorkGraph
from axia.shared.errors import AxiaError
from axia.shared.ids import ArtifactId, NodeId, RunId, stable_json_hash
from axia.source.records import ProviderResponseRecord


MANIFEST_MODES = frozenset({"quick", "standard", "deep"})
MANIFEST_STATUSES = frozenset({"new", "running", "complete", "failed", "cancelled"})
MANIFEST_NODE_STATUSES = frozenset({"accepted", "repaired", "rejected", "failed"})
RUN_MANIFEST_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "run_id",
        "created_at",
        "app_version",
        "user_request_hash",
        "model_profile",
        "prompt_hashes",
        "mode",
        "status",
        "canonical_request",
        "constitution",
        "work_graph",
        "node_results",
        "final_answer",
        "memory_candidates",
        "metrics",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "run_id": {"type": "string", "minLength": 1},
        "created_at": {"type": "string", "minLength": 1},
        "app_version": {"type": "string", "minLength": 1},
        "user_request_hash": {"type": "string", "minLength": 1},
        "model_profile": {"type": "object"},
        "prompt_hashes": {"type": "object"},
        "mode": {"type": "string", "enum": sorted(MANIFEST_MODES)},
        "status": {"type": "string", "enum": sorted(MANIFEST_STATUSES)},
        "canonical_request": {"type": "object"},
        "constitution": {"type": "object"},
        "work_graph": {"type": "object"},
        "node_results": {"type": "array"},
        "final_answer": {},
        "memory_candidates": {"type": "array"},
        "metrics": {"type": "object"},
    },
}


@dataclass(frozen=True)
class ModelProfileIdentity:
    """The selected profile's stable identity plus normalized provider details when available."""

    name: str
    profile_hash: str
    provider_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not isinstance(self.profile_hash, str) or not self.name.strip() or not self.profile_hash.strip():
            raise RunManifestFailure(
                kind="run_manifest_profile_identity_invalid",
                message="model profile identity requires a name and profile hash",
            )
        if any(
            not isinstance(key, str) or not isinstance(value, str) or not key.strip() or not value.strip()
            for key, value in self.provider_metadata.items()
        ):
            raise RunManifestFailure(
                kind="run_manifest_provider_metadata_invalid",
                message="provider metadata keys and values must be non-empty strings",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "profile_hash": self.profile_hash,
            "provider_metadata": dict(sorted(self.provider_metadata.items())),
        }


@dataclass(frozen=True)
class RunManifestNodeResult:
    """One saved node attempt, including the exact prompt and validation evidence used by replay."""

    node_id: NodeId
    attempt: int
    status: str
    input_hash: str
    prompt_hash: str
    artifact_id: ArtifactId | None
    artifact: TypedArtifact | None
    validation_errors: tuple[ValidationIssue, ...]
    scorecard: Scorecard | None
    provider_response: ProviderResponseRecord | None
    started_at: str
    ended_at: str

    def __post_init__(self) -> None:
        if self.attempt <= 0:
            raise RunManifestFailure(
                kind="run_manifest_node_attempt_invalid",
                message="node result attempts start at one",
            )
        if self.status not in MANIFEST_NODE_STATUSES:
            raise RunManifestFailure(
                kind="run_manifest_node_status_invalid",
                message=f"unsupported node result status {self.status!r}",
            )
        if not self.input_hash.strip() or not self.prompt_hash.strip():
            raise RunManifestFailure(
                kind="run_manifest_node_hash_missing",
                message="node results require input and prompt hashes",
            )
        if self.artifact is not None and self.artifact_id is None:
            raise RunManifestFailure(
                kind="run_manifest_artifact_identity_mismatch",
                message="a typed artifact requires its stable artifact ID",
            )
        if self.artifact is not None and self.validation_errors:
            raise RunManifestFailure(
                kind="run_manifest_artifact_validation_mismatch",
                message="a typed artifact cannot coexist with parse or schema validation errors",
            )
        if self.provider_response is not None:
            if any(
                not isinstance(key, str) or not isinstance(value, str) or not key.strip() or not value.strip()
                for key, value in self.provider_response.metadata.items()
            ):
                raise RunManifestFailure(
                    kind="run_manifest_provider_metadata_invalid",
                    message="provider response metadata keys and values must be non-empty strings",
                )
            expected_response_hash = stable_json_hash(
                {"text": self.provider_response.text, "metadata": dict(self.provider_response.metadata)}
            )
            if self.provider_response.content_hash != expected_response_hash:
                raise RunManifestFailure(
                    kind="run_manifest_provider_response_hash_mismatch",
                    message="provider response hash must match the saved response text and metadata",
                )
        if self.status in {"accepted", "repaired"} and self.artifact is None:
            raise RunManifestFailure(
                kind="run_manifest_accepted_artifact_missing",
                message="accepted and repaired node results require a typed artifact",
            )
        _require_timestamp(self.started_at, "run_manifest_node_started_at_invalid")
        _require_timestamp(self.ended_at, "run_manifest_node_ended_at_invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id.value,
            "attempt": self.attempt,
            "status": self.status,
            "input_hash": self.input_hash,
            "prompt_hash": self.prompt_hash,
            "output_hash": (
                self.provider_response.content_hash
                if self.provider_response is not None
                else self.artifact.content_hash if self.artifact is not None else None
            ),
            "artifact_id": self.artifact_id.value if self.artifact_id is not None else None,
            "artifact": dict(self.artifact.payload) if self.artifact is not None else None,
            "validation_errors": [
                {"path": issue.path, "rule": issue.rule, "message": issue.message}
                for issue in self.validation_errors
            ],
            "scorecard": self.scorecard.to_payload() if self.scorecard is not None else None,
            "provider_response": self.provider_response.to_payload() if self.provider_response is not None else None,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


@dataclass(frozen=True)
class RunManifest:
    """Versioned, immutable projection of the evidence required to inspect and replay one run."""

    run_id: RunId
    created_at: str
    app_version: str
    user_request_hash: str
    model_profile: ModelProfileIdentity
    prompt_hashes: Mapping[str, str]
    mode: str
    status: str
    canonical_request: CanonicalRequest
    constitution: TaskConstitution
    work_graph: WorkGraph
    node_results: tuple[RunManifestNodeResult, ...]
    final_answer: FinalAnswer | str | None
    memory_candidates: tuple[MemoryCandidate, ...]
    metrics: Mapping[str, object]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise RunManifestFailure(
                kind="run_manifest_schema_version_invalid",
                message="run manifests currently require schema version 1",
            )
        _require_timestamp(self.created_at, "run_manifest_created_at_invalid")
        if not self.app_version.strip() or not self.user_request_hash.strip():
            raise RunManifestFailure(
                kind="run_manifest_required_value_missing",
                message="run manifests require an app version and user request hash",
            )
        if self.mode not in MANIFEST_MODES or self.status not in MANIFEST_STATUSES:
            raise RunManifestFailure(
                kind="run_manifest_status_or_mode_invalid",
                message="run manifest mode and status must be admitted values",
            )
        if self.canonical_request.source_request_hash != self.user_request_hash:
            raise RunManifestFailure(
                kind="run_manifest_request_lineage_mismatch",
                message="canonical request must derive from the manifest user request hash",
            )
        if self.constitution.source_request_hash != self.user_request_hash:
            raise RunManifestFailure(
                kind="run_manifest_constitution_request_mismatch",
                message="constitution must derive from the manifest user request hash",
            )
        if self.constitution.canonical_request_hash != stable_json_hash(self.canonical_request.to_payload()):
            raise RunManifestFailure(
                kind="run_manifest_constitution_canonical_mismatch",
                message="constitution must derive from the saved canonical request",
            )
        if self.work_graph.constitution_revision_hash != self.constitution.revision_hash():
            raise RunManifestFailure(
                kind="run_manifest_graph_constitution_mismatch",
                message="work graph must derive from the saved constitution revision",
            )
        if any(
            not isinstance(name, str) or not isinstance(prompt_hash, str) or not name.strip() or not prompt_hash.strip()
            for name, prompt_hash in self.prompt_hashes.items()
        ):
            raise RunManifestFailure(
                kind="run_manifest_prompt_hash_invalid",
                message="prompt hash keys and values must be non-empty strings",
            )
        result_keys = [(result.node_id, result.attempt) for result in self.node_results]
        if len(set(result_keys)) != len(result_keys):
            raise RunManifestFailure(
                kind="run_manifest_duplicate_node_result",
                message="each node attempt may appear only once in a manifest",
            )
        graph_nodes = {node.node_id for node in self.work_graph.nodes}
        for result in self.node_results:
            if result.node_id not in graph_nodes:
                raise RunManifestFailure(
                    kind="run_manifest_unknown_node",
                    message="node result must belong to the saved work graph",
                )
            if self.prompt_hashes.get(prompt_hash_key(result.node_id, result.attempt)) != result.prompt_hash:
                raise RunManifestFailure(
                    kind="run_manifest_prompt_hash_missing",
                    message="every node result must have the matching manifest prompt hash",
                )
            if result.scorecard is not None:
                _validate_scorecard_lineage(self.run_id, result)
        artifact_ids = {result.artifact_id for result in self.node_results if result.artifact_id is not None}
        for candidate in self.memory_candidates:
            if candidate.source_run_id != self.run_id:
                raise RunManifestFailure(
                    kind="run_manifest_memory_candidate_lineage_mismatch",
                    message="memory candidates must originate from the manifest run",
                )
            if not set(candidate.source_artifact_ids).issubset(artifact_ids):
                raise RunManifestFailure(
                    kind="run_manifest_memory_candidate_artifact_mismatch",
                    message="memory candidates must cite artifacts present in the manifest",
                )
        rendered_final_answer = _render_final_answer(self.final_answer)
        if self.status == "complete" and not rendered_final_answer:
            raise RunManifestFailure(
                kind="run_manifest_final_answer_missing",
                message="a complete run requires a non-empty final answer",
            )
        if self.final_answer is not None and not rendered_final_answer:
            raise RunManifestFailure(
                kind="run_manifest_final_answer_invalid",
                message="final answers must be non-empty when present",
            )
        if isinstance(self.final_answer, FinalAnswer):
            if self.final_answer.source_run_id != self.run_id:
                raise RunManifestFailure(
                    kind="run_manifest_final_answer_lineage_mismatch",
                    message="structured final answers must originate from the manifest run",
                )
            accepted_artifact_ids = {
                result.artifact_id
                for result in self.node_results
                if result.status in {"accepted", "repaired"} and result.artifact_id is not None
            }
            if not {claim.source_artifact_id for claim in self.final_answer.claims}.issubset(accepted_artifact_ids):
                raise RunManifestFailure(
                    kind="run_manifest_final_answer_artifact_mismatch",
                    message="structured final answers must cite accepted manifest artifacts",
                )
        try:
            stable_json_hash(self.metrics)
        except (TypeError, ValueError) as error:
            raise RunManifestFailure(
                kind="run_manifest_metrics_not_serializable",
                message="manifest metrics must be JSON serializable",
            ) from error

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id.value,
            "created_at": self.created_at,
            "app_version": self.app_version,
            "user_request_hash": self.user_request_hash,
            "model_profile": self.model_profile.to_payload(),
            "prompt_hashes": dict(sorted(self.prompt_hashes.items())),
            "mode": self.mode,
            "status": self.status,
            "canonical_request": self.canonical_request.to_payload(),
            "constitution": self.constitution.to_payload(),
            "work_graph": self.work_graph.to_payload(),
            "node_results": [result.to_payload() for result in self.node_results],
            "final_answer": self.final_answer.to_payload() if isinstance(self.final_answer, FinalAnswer) else self.final_answer,
            "memory_candidates": [candidate.to_payload() for candidate in self.memory_candidates],
            "metrics": dict(self.metrics),
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())


@dataclass(frozen=True)
class RunManifestFailure(AxiaError):
    """A deterministic failure while forming a public run-manifest projection."""


def prompt_hash_key(node_id: NodeId, attempt: int) -> str:
    if attempt <= 0:
        raise RunManifestFailure(
            kind="run_manifest_node_attempt_invalid",
            message="prompt hash keys require attempts starting at one",
        )
    return f"{node_id.value}:attempt:{attempt}"


def _validate_scorecard_lineage(run_id: RunId, result: RunManifestNodeResult) -> None:
    assert result.scorecard is not None
    if result.scorecard.source_run_id != run_id or result.scorecard.source_node_id != result.node_id:
        raise RunManifestFailure(
            kind="run_manifest_scorecard_lineage_mismatch",
            message="scorecards must belong to their manifest run and node result",
        )
    if result.artifact_id is None or result.scorecard.source_artifact_id != result.artifact_id:
        raise RunManifestFailure(
            kind="run_manifest_scorecard_artifact_mismatch",
            message="scorecards must reference the node result artifact",
        )


def _require_timestamp(value: str, kind: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RunManifestFailure(kind=kind, message="timestamps must be ISO-8601 values") from error


def _render_final_answer(final_answer: FinalAnswer | str | None) -> str | None:
    if final_answer is None:
        return None
    if isinstance(final_answer, FinalAnswer):
        return final_answer.render().strip()
    if isinstance(final_answer, str):
        return final_answer.strip()
    raise RunManifestFailure(
        kind="run_manifest_final_answer_invalid",
        message="final answers must be strings or trace-grounded final-answer records",
    )
