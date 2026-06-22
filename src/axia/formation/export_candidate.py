from __future__ import annotations

from dataclasses import dataclass

from axia.shared.ids import ArtifactId, CandidateId


@dataclass(frozen=True)
class ExportCandidate:
    """A trace-derived proposal for external evaluation or data curation, never a dataset write."""

    candidate_id: CandidateId
    candidate_type: str
    source_run_id: str
    source_artifact_ids: tuple[ArtifactId, ...]
    final_answer: str
    proposed_for: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id.value,
            "candidate_type": self.candidate_type,
            "source_run_id": self.source_run_id,
            "source_artifact_ids": [artifact_id.value for artifact_id in self.source_artifact_ids],
            "final_answer": self.final_answer,
            "proposed_for": list(self.proposed_for),
        }
