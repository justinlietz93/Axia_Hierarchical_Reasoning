from __future__ import annotations

import json

from axia.boundary.ports.model_provider import ModelMessage, ModelProvider, ModelRequest
from axia.formation.final_answer import (
    FINAL_SYNTHESIS_SCHEMA,
    AcceptedArtifact,
    FinalAnswer,
    FinalClaim,
    FinalSynthesisContext,
    FinalSynthesisFailure,
)
from axia.formation.structured_output import parse_and_validate_json_object
from axia.projection.run_manifest import RunManifest
from axia.shared.ids import ArtifactId, stable_json_hash


def form_final_synthesis_context(
    manifest: RunManifest,
    *,
    unresolved_caveats: tuple[str, ...] = (),
    style_constraints: tuple[str, ...] = ("Follow the requested output format.",),
) -> FinalSynthesisContext:
    """Admit only validated, scorecard-accepted artifacts from one saved run manifest."""

    accepted_artifacts = tuple(
        AcceptedArtifact(
            artifact_id=result.artifact_id,
            source_node_id=result.node_id,
            artifact=result.artifact,
            scorecard=result.scorecard,
        )
        for result in manifest.node_results
        if (
            result.status in {"accepted", "repaired"}
            and result.artifact_id is not None
            and result.artifact is not None
            and not result.validation_errors
            and result.scorecard is not None
            and result.scorecard.decision == "accept"
        )
    )
    return FinalSynthesisContext(
        source_run_id=manifest.run_id,
        constitution=manifest.constitution,
        requested_format=manifest.canonical_request.output_format,
        style_constraints=style_constraints,
        accepted_artifacts=accepted_artifacts,
        unresolved_caveats=unresolved_caveats,
    )


def compile_final_synthesis_request(context: FinalSynthesisContext) -> ModelRequest:
    """Compile one finalizer call whose allowed source material is explicit and trace-derived."""

    prompt = "\n\n".join(
        (
            "ROLE\nYou are Axia's finalizer. Produce the final response only from accepted artifact evidence.",
            (
                "CONTRACT\nReturn valid JSON only. Each claim text must be copied exactly from its cited accepted artifact. "
                "Each evidence excerpt must be copied exactly from the same artifact. Do not cite rejected artifacts, add a claim, "
                "or add a caveat that is absent from the supplied unresolved caveats."
            ),
            "SYNTHESIS_CONTEXT\n" + _canonical_json(context.to_payload()),
            "OUTPUT_SCHEMA\n" + _canonical_json(FINAL_SYNTHESIS_SCHEMA),
        )
    )
    return ModelRequest(
        messages=(ModelMessage(role="system", content=prompt),),
        output_schema=FINAL_SYNTHESIS_SCHEMA,
        metadata={
            "stage": "final_synthesis",
            "source_run_id": context.source_run_id.value,
            "prompt_hash": stable_json_hash({"prompt": prompt}),
        },
    )


def execute_final_synthesis(context: FinalSynthesisContext, provider: ModelProvider) -> FinalAnswer:
    """Generate and verify one final response without allowing raw provider prose to become product truth."""

    response = provider.generate(compile_final_synthesis_request(context))
    return parse_final_synthesis_response(context, response.text)


def parse_final_synthesis_response(context: FinalSynthesisContext, response_text: str) -> FinalAnswer:
    """Reject malformed, unsupported, or caveat-inventing finalizer output."""

    parsed = parse_and_validate_json_object(response_text, FINAL_SYNTHESIS_SCHEMA)
    if not parsed.accepted:
        issue = parsed.validation_errors[0]
        raise FinalSynthesisFailure(kind="final_synthesis_schema_invalid", message=f"{issue.path} {issue.message}")
    assert parsed.payload is not None
    raw_claims = parsed.payload["claims"]
    raw_caveats = parsed.payload["unresolved_caveats"]
    assert isinstance(raw_claims, list) and isinstance(raw_caveats, list)
    claims = tuple(_claim_from_payload(item) for item in raw_claims)
    caveats = tuple(_required_string(item, "final_synthesis_caveat_invalid") for item in raw_caveats)
    _validate_claims(context, claims)
    if not set(caveats).issubset(set(context.unresolved_caveats)):
        raise FinalSynthesisFailure(
            kind="final_synthesis_unsupported_caveat",
            message="final answers may include only supplied unresolved caveats",
        )
    return FinalAnswer(
        source_run_id=context.source_run_id,
        claims=claims,
        unresolved_caveats=caveats,
        requested_format=context.requested_format,
        style_constraints=context.style_constraints,
    )


def _claim_from_payload(value: object) -> FinalClaim:
    if not isinstance(value, dict):
        raise FinalSynthesisFailure(kind="final_synthesis_claim_invalid", message="final claims must be objects")
    text = _required_string(value.get("text"), "final_synthesis_claim_invalid")
    source_artifact_id = _required_string(value.get("source_artifact_id"), "final_synthesis_claim_invalid")
    evidence_excerpt = _required_string(value.get("evidence_excerpt"), "final_synthesis_claim_invalid")
    try:
        artifact_id = ArtifactId.from_value(source_artifact_id)
    except ValueError as error:
        raise FinalSynthesisFailure(
            kind="final_synthesis_claim_invalid",
            message="final claim source artifact IDs must use the Axia artifact ID format",
        ) from error
    return FinalClaim(text=text, source_artifact_id=artifact_id, evidence_excerpt=evidence_excerpt)


def _validate_claims(context: FinalSynthesisContext, claims: tuple[FinalClaim, ...]) -> None:
    artifacts_by_id = {artifact.artifact_id: artifact for artifact in context.accepted_artifacts}
    for claim in claims:
        artifact = artifacts_by_id.get(claim.source_artifact_id)
        if artifact is None:
            raise FinalSynthesisFailure(
                kind="final_synthesis_rejected_artifact",
                message="final claims may cite only artifacts accepted in the synthesis context",
            )
        serialized_artifact = artifact.serialized_content()
        if claim.text not in serialized_artifact or claim.evidence_excerpt not in serialized_artifact:
            raise FinalSynthesisFailure(
                kind="final_synthesis_unsupported_claim",
                message="final claims and their excerpts must be present in the cited accepted artifact",
            )


def _required_string(value: object, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinalSynthesisFailure(kind=kind, message="final synthesis text values must be non-empty strings")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
