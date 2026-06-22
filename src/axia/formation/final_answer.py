from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from axia.formation.micro_agent import TypedArtifact
from axia.formation.scorecard import Scorecard
from axia.formation.task_constitution import TaskConstitution
from axia.shared.errors import AxiaError
from axia.shared.ids import ArtifactId, NodeId, RunId, stable_json_hash


FINAL_SYNTHESIS_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims", "unresolved_caveats"],
    "properties": {
        "claims": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "source_artifact_id", "evidence_excerpt"],
                "properties": {
                    "text": {"type": "string", "minLength": 1},
                    "source_artifact_id": {"type": "string", "minLength": 1},
                    "evidence_excerpt": {"type": "string", "minLength": 1},
                },
            },
        },
        "unresolved_caveats": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}


@dataclass(frozen=True)
class AcceptedArtifact:
    """One artifact that has survived node validation and scorecard acceptance."""

    artifact_id: ArtifactId
    source_node_id: NodeId
    artifact: TypedArtifact
    scorecard: Scorecard

    def __post_init__(self) -> None:
        if self.scorecard.source_artifact_id != self.artifact_id or self.scorecard.source_node_id != self.source_node_id:
            raise FinalSynthesisFailure(
                kind="final_synthesis_artifact_lineage_mismatch",
                message="accepted artifacts must preserve their scorecard artifact and node lineage",
            )
        if self.scorecard.decision != "accept":
            raise FinalSynthesisFailure(
                kind="final_synthesis_artifact_not_accepted",
                message="final synthesis may use only scorecard-accepted artifacts",
            )

    def serialized_content(self) -> str:
        return json.dumps(self.artifact.payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)

    def to_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id.value,
            "source_node_id": self.source_node_id.value,
            "artifact": dict(self.artifact.payload),
            "scorecard": self.scorecard.to_payload(),
        }


@dataclass(frozen=True)
class FinalSynthesisContext:
    """The entire trace-derived input admitted to one finalizer exchange."""

    source_run_id: RunId
    constitution: TaskConstitution
    requested_format: str
    style_constraints: tuple[str, ...]
    accepted_artifacts: tuple[AcceptedArtifact, ...]
    unresolved_caveats: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.requested_format.strip():
            raise FinalSynthesisFailure(
                kind="final_synthesis_requested_format_missing",
                message="final synthesis requires the requested output format",
            )
        if not self.style_constraints or any(not value.strip() for value in self.style_constraints):
            raise FinalSynthesisFailure(
                kind="final_synthesis_style_constraints_invalid",
                message="final synthesis requires non-empty user-facing style constraints",
            )
        if not self.accepted_artifacts:
            raise FinalSynthesisFailure(
                kind="final_synthesis_no_accepted_artifacts",
                message="final synthesis requires at least one accepted artifact",
            )
        artifact_ids = [artifact.artifact_id for artifact in self.accepted_artifacts]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise FinalSynthesisFailure(
                kind="final_synthesis_duplicate_artifact",
                message="accepted artifacts must appear only once in final synthesis context",
            )
        if any(artifact.scorecard.source_run_id != self.source_run_id for artifact in self.accepted_artifacts):
            raise FinalSynthesisFailure(
                kind="final_synthesis_run_lineage_mismatch",
                message="accepted artifacts must originate from the synthesis run",
            )
        if any(not caveat.strip() for caveat in self.unresolved_caveats):
            raise FinalSynthesisFailure(
                kind="final_synthesis_caveat_invalid",
                message="unresolved caveats must not contain blank values",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "constitution": self.constitution.to_payload(),
            "accepted_artifacts": [artifact.to_payload() for artifact in self.accepted_artifacts],
            "requested_format": self.requested_format,
            "style_constraints": list(self.style_constraints),
            "unresolved_caveats": list(self.unresolved_caveats),
        }


@dataclass(frozen=True)
class FinalClaim:
    """One user-facing claim that can be verified directly against an accepted artifact."""

    text: str
    source_artifact_id: ArtifactId
    evidence_excerpt: str

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.evidence_excerpt.strip():
            raise FinalSynthesisFailure(
                kind="final_synthesis_claim_invalid",
                message="final claims require non-empty text and evidence excerpts",
            )

    def to_payload(self) -> dict[str, str]:
        return {
            "text": self.text,
            "source_artifact_id": self.source_artifact_id.value,
            "evidence_excerpt": self.evidence_excerpt,
        }


@dataclass(frozen=True)
class FinalAnswer:
    """A final answer rendered only from trace-supported claims and declared caveats."""

    source_run_id: RunId
    claims: tuple[FinalClaim, ...]
    unresolved_caveats: tuple[str, ...]
    requested_format: str
    style_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claims:
            raise FinalSynthesisFailure(
                kind="final_synthesis_claims_missing",
                message="final answers require at least one supported claim",
            )
        if any(not caveat.strip() for caveat in self.unresolved_caveats):
            raise FinalSynthesisFailure(
                kind="final_synthesis_caveat_invalid",
                message="final answer caveats must not contain blank values",
            )

    def render(self) -> str:
        answer = "\n\n".join(claim.text for claim in self.claims)
        if self.unresolved_caveats:
            answer = answer + "\n\nCaveats:\n" + "\n".join(f"- {caveat}" for caveat in self.unresolved_caveats)
        return answer

    def to_payload(self) -> dict[str, object]:
        return {
            "source_run_id": self.source_run_id.value,
            "claims": [claim.to_payload() for claim in self.claims],
            "unresolved_caveats": list(self.unresolved_caveats),
            "requested_format": self.requested_format,
            "style_constraints": list(self.style_constraints),
            "rendered_answer": self.render(),
        }

    def content_hash(self) -> str:
        return stable_json_hash(self.to_payload())


@dataclass(frozen=True)
class FinalSynthesisFailure(AxiaError):
    """A deterministic refusal to synthesize an unsupported final answer."""
