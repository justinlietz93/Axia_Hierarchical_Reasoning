from __future__ import annotations

from axia.boundary.ports.export_candidate_sink import ExportCandidateSink
from axia.formation.export_candidate import ExportCandidate
from axia.formation.final_answer import FinalAnswer
from axia.projection.run_manifest import RunManifest
from axia.shared.ids import CandidateId, stable_json_hash


def form_export_candidates(manifest: RunManifest) -> tuple[ExportCandidate, ExportCandidate]:
    """Form external curation proposals only from a structured trace-grounded final answer."""

    if not isinstance(manifest.final_answer, FinalAnswer):
        raise ValueError("export candidates require a trace-grounded structured final answer")
    artifact_ids = tuple(claim.source_artifact_id for claim in manifest.final_answer.claims)
    identity = {"run_id": manifest.run_id.value, "artifacts": [item.value for item in artifact_ids]}
    return (
        ExportCandidate(CandidateId.from_value(f"candidate_reasoning_{stable_json_hash(identity)[:16]}"), "reasoning_example", manifest.run_id.value, artifact_ids, manifest.final_answer.render(), ("regression", "prompt_improvement", "external_export")),
        ExportCandidate(CandidateId.from_value(f"candidate_training_{stable_json_hash(identity)[:16]}"), "training_slice", manifest.run_id.value, artifact_ids, manifest.final_answer.render(), ("external_export",)),
    )


def emit_export_candidates(
    candidates: tuple[ExportCandidate, ...],
    sink: ExportCandidateSink | None = None,
    *,
    user_approved: bool = False,
) -> tuple[ExportCandidate, ...]:
    """Deliver proposals only after explicit approval; Axia never writes datasets itself."""

    if sink is not None and not user_approved:
        raise PermissionError("external export requires explicit user approval")
    if sink is not None:
        for candidate in candidates:
            sink.emit(candidate)
    return candidates
