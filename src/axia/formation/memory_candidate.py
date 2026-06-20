from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from axia.shared.errors import AxiaError
from axia.shared.ids import ArtifactId, CandidateId, RunId, stable_json_hash


MEMORY_CANDIDATE_TYPES = frozenset(
    {
        "preference",
        "project",
        "fact",
        "pattern",
        "correction",
        "plan_template",
        "failure_case",
    }
)
MEMORY_CANDIDATE_SCOPES = frozenset({"global", "project", "conversation", "run"})
MEMORY_CANDIDATE_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "candidate_id",
        "type",
        "proposed_scope",
        "content",
        "source_run_id",
        "source_artifact_ids",
        "confidence",
        "reason",
        "caveats",
        "created_at",
        "tags",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "candidate_id": {"type": "string"},
        "type": {"type": "string", "enum": sorted(MEMORY_CANDIDATE_TYPES)},
        "proposed_scope": {"type": "string", "enum": sorted(MEMORY_CANDIDATE_SCOPES)},
        "content": {"type": "string", "minLength": 1},
        "source_run_id": {"type": "string"},
        "source_artifact_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "minLength": 1},
        "caveats": {"type": "array", "items": {"type": "string"}},
        "created_at": {"type": "string", "format": "date-time"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass(frozen=True)
class MemoryCandidate:
    """A trace-derived proposal for an external memory authority to evaluate."""

    candidate_id: CandidateId
    candidate_type: str
    proposed_scope: str
    content: str
    source_run_id: RunId
    source_artifact_ids: tuple[ArtifactId, ...]
    confidence: float
    reason: str
    caveats: tuple[str, ...]
    created_at: str
    tags: tuple[str, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise MemoryCandidateFailure(
                kind="memory_candidate_schema_version_invalid",
                message="memory candidate projections currently require schema version 1",
            )
        if self.candidate_type not in MEMORY_CANDIDATE_TYPES:
            raise MemoryCandidateFailure(
                kind="memory_candidate_type_invalid",
                message=f"unsupported memory candidate type {self.candidate_type!r}",
            )
        if self.proposed_scope not in MEMORY_CANDIDATE_SCOPES:
            raise MemoryCandidateFailure(
                kind="memory_candidate_scope_invalid",
                message=f"unsupported memory candidate scope {self.proposed_scope!r}",
            )
        if not self.content.strip() or not self.reason.strip():
            raise MemoryCandidateFailure(
                kind="memory_candidate_missing_value",
                message="memory candidates require non-empty content and reason",
            )
        if not self.source_artifact_ids:
            raise MemoryCandidateFailure(
                kind="memory_candidate_missing_lineage",
                message="memory candidates require at least one source artifact ID",
            )
        if len(set(self.source_artifact_ids)) != len(self.source_artifact_ids):
            raise MemoryCandidateFailure(
                kind="memory_candidate_duplicate_lineage",
                message="memory candidate source artifact IDs must be unique",
            )
        if not 0 <= self.confidence <= 1:
            raise MemoryCandidateFailure(
                kind="memory_candidate_confidence_invalid",
                message="memory candidate confidence must be within [0, 1]",
            )
        for field_name, values in (("caveats", self.caveats), ("tags", self.tags)):
            if any(not value.strip() for value in values):
                raise MemoryCandidateFailure(
                    kind="memory_candidate_invalid_text",
                    message=f"memory candidate {field_name} must not contain blank values",
                )
            if len(set(values)) != len(values):
                raise MemoryCandidateFailure(
                    kind="memory_candidate_duplicate_text",
                    message=f"memory candidate {field_name} must be unique",
                )
        try:
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise MemoryCandidateFailure(
                kind="memory_candidate_created_at_invalid",
                message="memory candidate created_at must be an ISO-8601 timestamp",
            ) from error

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id.value,
            "type": self.candidate_type,
            "proposed_scope": self.proposed_scope,
            "content": self.content,
            "source_run_id": self.source_run_id.value,
            "source_artifact_ids": [artifact_id.value for artifact_id in self.source_artifact_ids],
            "confidence": self.confidence,
            "reason": self.reason,
            "caveats": list(self.caveats),
            "created_at": self.created_at,
            "tags": list(self.tags),
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())


@dataclass(frozen=True)
class MemoryCandidateFailure(AxiaError):
    """A deterministic failure while forming a memory-candidate projection."""
