from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from time import monotonic
from typing import Callable, Mapping

from axia import __version__
from axia.boundary.ports.model_provider import ModelProvider, ModelRequest, ModelResponse
from axia.boundary.ports.run_store import RunStore, RunTraceRecord
from axia.formation.context_pack import ContextReference, build_context_pack
from axia.formation.final_answer import FinalAnswer, FinalClaim
from axia.formation.micro_agent import (
    ArtifactEvaluator,
    MicroAgentContract,
    MicroAgentEvaluation,
    NodeValidationResult,
    TypedArtifact,
    require_valid_node_output,
    validate_micro_agent_response,
)
from axia.formation.canonical_request import CanonicalRequest, CanonicalRequestFailure, require_source_alignment
from axia.formation.scorecard import ArtifactScoreInput, score_artifact
from axia.formation.structured_output import ValidationIssue
from axia.formation.task_constitution import DEFAULT_LIMITS, TaskConstitution, build_task_constitution
from axia.formation.work_graph import WorkGraph, WorkNode, build_standard_work_graph
from axia.operation.canonical_request_builder import (
    build_raw_request_fallback,
    compile_canonical_request_request,
    parse_canonical_request_response,
)
from axia.operation.micro_agent_executor import compile_micro_agent_request
from axia.operation.run_manifest_recorder import record_run_manifest
from axia.projection.run_manifest import (
    ModelProfileIdentity,
    RunManifest,
    RunManifestNodeResult,
    prompt_hash_key,
)
from axia.shared.errors import AxiaError
from axia.shared.ids import ArtifactId, NodeId, RunId, ScorecardId, stable_json_hash
from axia.source.records import ProviderResponseRecord, RequestRecord


@dataclass(frozen=True)
class RunExecution:
    """One completed, persisted reasoning run with its trace-grounded final answer."""

    manifest: RunManifest

    @property
    def final_answer_text(self) -> str:
        final_answer = self.manifest.final_answer
        if isinstance(final_answer, FinalAnswer):
            return final_answer.render()
        return str(final_answer or "")


@dataclass(frozen=True)
class RunExecutionFailure(AxiaError):
    """A bounded execution could not admit a complete replayable result."""


@dataclass(frozen=True)
class _ExecutedNode:
    node: WorkNode
    result: RunManifestNodeResult


class _AcceptingEvaluator(ArtifactEvaluator):
    def evaluate(self, artifact: TypedArtifact) -> MicroAgentEvaluation:
        return MicroAgentEvaluation(accepted=True, reasons=("schema validation is handled by the controller",))


class RunController:
    """Execute the admitted local reasoning graph without importing provider-specific mechanisms."""

    def __init__(
        self,
        provider: ModelProvider,
        model_profile: ModelProfileIdentity,
        *,
        run_store: RunStore | None = None,
        run_id_factory: Callable[[], RunId] = RunId.new,
        clock: Callable[[], float] = monotonic,
        timestamp: Callable[[], str] | None = None,
    ) -> None:
        self._provider = provider
        self._model_profile = model_profile
        self._run_store = run_store
        self._run_id_factory = run_id_factory
        self._clock = clock
        self._timestamp = timestamp or _utc_timestamp

    def execute(self, raw_request: str, *, mode: str = "standard") -> RunExecution:
        """Form, validate, score, and persist one bounded reasoning run."""

        if mode not in {"quick", "standard", "deep"}:
            raise RunExecutionFailure(kind="run_mode_invalid", message=f"unsupported run mode {mode!r}")
        request = RequestRecord.from_text(raw_request)
        if not request.raw_text.strip():
            raise RunExecutionFailure(kind="run_request_missing", message="a run requires a non-empty request")

        started_at = self._clock()
        run_id = self._run_id_factory()
        limits = DEFAULT_LIMITS["brief" if mode == "quick" else mode]
        calls_used = 0

        def generate(model_request: ModelRequest) -> ModelResponse:
            nonlocal calls_used
            if calls_used >= limits.max_model_calls:
                raise RunExecutionFailure(
                    kind="run_model_call_limit_exhausted",
                    message="the task constitution model-call limit was reached",
                )
            _require_time_limit(started_at, limits.max_seconds, self._clock)
            response = self._provider.generate(model_request)
            calls_used += 1
            _require_time_limit(started_at, limits.max_seconds, self._clock)
            return response

        canonical_rejections: list[tuple[ModelRequest, ModelResponse, CanonicalRequestFailure]] = []
        canonical_request = None
        canonical_request_model_request = None
        canonical_response = None
        validation_feedback = None
        for _ in range(2):
            candidate_request = compile_canonical_request_request(
                request,
                validation_feedback=validation_feedback,
            )
            candidate_response = generate(candidate_request)
            try:
                canonical_request = parse_canonical_request_response(request, candidate_response.text)
                require_source_alignment(request, canonical_request)
            except CanonicalRequestFailure as error:
                canonical_rejections.append((candidate_request, candidate_response, error))
                validation_feedback = error.message
                continue
            canonical_request_model_request = candidate_request
            canonical_response = candidate_response
            break
        canonicalization_fallback = canonical_request is None
        if canonicalization_fallback:
            canonical_request = build_raw_request_fallback(
                request,
                expected_depth="brief" if mode == "quick" else mode,
            )
        constitution = build_task_constitution(canonical_request, limits=limits)
        graph = build_standard_work_graph(constitution)
        nodes = {node.kind: node for node in graph.nodes}

        executed: list[_ExecutedNode] = []

        def require_admitted(executed_node: _ExecutedNode, stage: str) -> None:
            try:
                _require_accepted(executed_node.result, stage)
            except RunExecutionFailure as error:
                self._persist_failed_run(
                    run_id=run_id,
                    request=request,
                    mode=mode,
                    canonical_request=canonical_request,
                    constitution=constitution,
                    graph=graph,
                    results=tuple(item.result for item in executed),
                    model_calls=calls_used,
                    started_at=started_at,
                    error=error,
                )
                raise RunExecutionFailure(
                    kind=error.kind,
                    message=f"{error.message} Stored failed run: {run_id.value}",
                ) from error

        for attempt, (rejected_request, rejected_response, error) in enumerate(canonical_rejections, start=1):
            executed.append(
                self._record_rejected_model_node(
                    node=nodes["canonicalize"],
                    attempt=attempt,
                    input_material={"source_request_hash": request.content_hash},
                    prompt_hash=_required_prompt_hash(rejected_request),
                    response=rejected_response,
                    validation_errors=(ValidationIssue(path="$", rule="canonical_request", message=error.message),),
                )
            )
        canonical_artifact = TypedArtifact.from_payload(canonical_request.to_payload())
        if canonicalization_fallback:
            canonical_node = self._record_deterministic_node(
                run_id=run_id,
                node=nodes["canonicalize"],
                attempt=len(canonical_rejections) + 1,
                input_material={"source_request_hash": request.content_hash, "fallback": "raw_request"},
                artifact=canonical_artifact,
                constitution=constitution,
                evidence_reference_ids=(f"request_{request.content_hash}",),
            )
        else:
            assert canonical_request_model_request is not None and canonical_response is not None
            canonical_node = self._record_node(
                run_id=run_id,
                node=nodes["canonicalize"],
                attempt=len(canonical_rejections) + 1,
                input_material={"source_request_hash": request.content_hash},
                prompt_hash=_required_prompt_hash(canonical_request_model_request),
                artifact=canonical_artifact,
                constitution=constitution,
                evidence_reference_ids=(f"request_{request.content_hash}",),
                provider_response=canonical_response,
            )
        executed.append(canonical_node)
        require_admitted(canonical_node, "canonicalize")

        constitution_artifact = TypedArtifact.from_payload(constitution.to_payload())
        constitute_node = self._record_deterministic_node(
            run_id=run_id,
            node=nodes["constitute"],
            input_material=canonical_artifact.payload,
            artifact=constitution_artifact,
            constitution=constitution,
            evidence_reference_ids=(canonical_node.result.artifact_id.value,),
        )
        executed.append(constitute_node)
        require_admitted(constitute_node, "constitute")

        retrieval_artifact = TypedArtifact.from_payload(
            {
                "task_mission": constitution.mission,
                "evidence": [],
                "caveats": ["No external context provider is configured for this standalone run."],
            }
        )
        retrieve_node = self._record_deterministic_node(
            run_id=run_id,
            node=nodes["retrieve"],
            input_material=constitution_artifact.payload,
            artifact=retrieval_artifact,
            constitution=constitution,
            evidence_reference_ids=(constitute_node.result.artifact_id.value,),
        )
        executed.append(retrieve_node)
        require_admitted(retrieve_node, "retrieve")
        retrieved_evidence = ContextReference.from_content(
            scope="retrieved_evidence",
            source_type="evidence",
            reference_id="evidence_no_external_context",
            content={"evidence": [], "caveats": retrieval_artifact.payload["caveats"]},
        )

        if mode == "quick":
            plan_artifact = TypedArtifact.from_payload(_deterministic_plan(canonical_request, constitution))
            plan_node = self._record_deterministic_node(
                run_id=run_id,
                node=nodes["plan"],
                input_material={"constitution": constitution_artifact.payload, "evidence": retrieval_artifact.payload},
                artifact=plan_artifact,
                constitution=constitution,
                evidence_reference_ids=(retrieve_node.result.artifact_id.value,),
            )
        else:
            plan_attempts = self._execute_micro_agent_node(
                run_id=run_id,
                node=nodes["plan"],
                constitution=constitution,
                prior_artifacts=(),
                context_records=(retrieved_evidence,),
                role_prompt=_plan_prompt(),
                generate=generate,
                evidence_reference_ids=(retrieve_node.result.artifact_id.value,),
            )
            executed.extend(plan_attempts)
            plan_node = plan_attempts[-1]
        if mode == "quick":
            executed.append(plan_node)
        require_admitted(plan_node, "plan")

        plan_reference = _artifact_reference("plan", plan_node.result)
        draft_attempts = self._execute_micro_agent_node(
            run_id=run_id,
            node=nodes["draft"],
            constitution=constitution,
            prior_artifacts=(plan_reference,),
            context_records=(),
            role_prompt=_draft_prompt(),
            generate=generate,
            evidence_reference_ids=(plan_node.result.artifact_id.value,),
        )
        executed.extend(draft_attempts)
        draft_node = draft_attempts[-1]
        require_admitted(draft_node, "draft")

        draft_reference = _draft_context_reference(draft_node.result)
        if mode == "quick":
            critique_artifact = TypedArtifact.from_payload(_deterministic_critique(constitution))
            critique_node = self._record_deterministic_node(
                run_id=run_id,
                node=nodes["critique"],
                input_material=draft_node.result.artifact.payload,
                artifact=critique_artifact,
                constitution=constitution,
                evidence_reference_ids=(draft_node.result.artifact_id.value,),
            )
        else:
            critique_attempts = self._execute_micro_agent_node(
                run_id=run_id,
                node=nodes["critique"],
                constitution=constitution,
                prior_artifacts=(draft_reference,),
                context_records=(),
                role_prompt=_critique_prompt(),
                generate=generate,
                evidence_reference_ids=(draft_node.result.artifact_id.value,),
            )
            executed.extend(critique_attempts)
            critique_node = critique_attempts[-1]
        if mode == "quick":
            executed.append(critique_node)
        require_admitted(critique_node, "critique")

        if draft_node.result.status == "accepted":
            repair_node = self._record_deterministic_node(
                run_id=run_id,
                node=nodes["repair"],
                input_material={"draft": draft_node.result.artifact.payload, "critique": critique_node.result.artifact.payload},
                artifact=TypedArtifact.from_payload(dict(draft_node.result.artifact.payload)),
                constitution=constitution,
                evidence_reference_ids=(draft_node.result.artifact_id.value, critique_node.result.artifact_id.value),
            )
        elif draft_node.result.scorecard is not None and draft_node.result.scorecard.decision == "repair":
            critique_evidence = ContextReference.from_content(
                scope="relevant_evidence",
                source_type="evidence",
                reference_id=critique_node.result.artifact_id.value,
                content=critique_node.result.artifact.payload,
            )
            repair_node = self._execute_repair_node(
                run_id=run_id,
                node=nodes["repair"],
                constitution=constitution,
                draft_node=draft_node,
                relevant_evidence=(critique_evidence,),
                generate=generate,
            )
        else:
            raise RunExecutionFailure(
                kind="run_draft_not_repairable",
                message="the draft did not meet acceptance and its score policy did not admit bounded repair",
            )
        executed.append(repair_node)
        require_admitted(repair_node, "repair")

        repaired_reference = _artifact_reference("repaired_draft", repair_node.result)
        verified_artifact = TypedArtifact.from_payload(dict(repair_node.result.artifact.payload))
        verify_node = self._record_deterministic_node(
            run_id=run_id,
            node=nodes["verify"],
            input_material={
                "repaired_draft": repair_node.result.artifact.payload,
                "evidence": retrieval_artifact.payload,
            },
            artifact=verified_artifact,
            constitution=constitution,
            evidence_reference_ids=(repair_node.result.artifact_id.value, retrieved_evidence.reference_id),
        )
        executed.append(verify_node)
        require_admitted(verify_node, "verify")

        answer_text = _artifact_answer(verify_node.result.artifact)
        final_answer = FinalAnswer(
            source_run_id=run_id,
            claims=(
                FinalClaim(
                    text=answer_text,
                    source_artifact_id=verify_node.result.artifact_id,
                    evidence_excerpt=answer_text,
                ),
            ),
            unresolved_caveats=_artifact_caveats(verify_node.result.artifact),
            requested_format=canonical_request.output_format,
            style_constraints=("Follow the requested output format.",),
        )
        final_artifact = TypedArtifact.from_payload(
            {
                "task_mission": constitution.mission,
                "answer": final_answer.render(),
                "source_artifact_id": verify_node.result.artifact_id.value,
            }
        )
        final_node = self._record_deterministic_node(
            run_id=run_id,
            node=nodes["final"],
            input_material={"verified_artifact": verify_node.result.artifact.payload},
            artifact=final_artifact,
            constitution=constitution,
            evidence_reference_ids=(verify_node.result.artifact_id.value,),
        )
        executed.append(final_node)
        require_admitted(final_node, "final")

        memory_artifact = TypedArtifact.from_payload(
            {
                "task_mission": constitution.mission,
                "emitted": False,
                "reason": "No external memory-candidate sink is configured for this standalone run.",
            }
        )
        memory_node = self._record_deterministic_node(
            run_id=run_id,
            node=nodes["emit_memory_candidate"],
            input_material=final_artifact.payload,
            artifact=memory_artifact,
            constitution=constitution,
            evidence_reference_ids=(final_node.result.artifact_id.value,),
        )
        executed.append(memory_node)
        require_admitted(memory_node, "memory_candidates")

        created_at = self._timestamp()
        results = tuple(item.result for item in executed)
        manifest = RunManifest(
            run_id=run_id,
            created_at=created_at,
            app_version=__version__,
            user_request_hash=request.content_hash,
            model_profile=self._model_profile,
            prompt_hashes={prompt_hash_key(result.node_id, result.attempt): result.prompt_hash for result in results},
            mode=mode,
            status="complete",
            canonical_request=canonical_request,
            constitution=constitution,
            work_graph=graph,
            node_results=results,
            final_answer=final_answer,
            memory_candidates=(),
            metrics={
                "model_calls": calls_used,
                "duration_seconds": round(self._clock() - started_at, 6),
                "external_context_provider": False,
                "canonicalization_fallback": canonicalization_fallback,
            },
        )
        if self._run_store is not None:
            record_run_manifest(manifest, self._run_store)
            self._record_trace_evidence(run_id, results)
        return RunExecution(manifest=manifest)

    def _execute_micro_agent_node(
        self,
        *,
        run_id: RunId,
        node: WorkNode,
        constitution: TaskConstitution,
        prior_artifacts: tuple[ContextReference, ...],
        context_records: tuple[ContextReference, ...],
        role_prompt: str,
        generate: Callable[[ModelRequest], ModelResponse],
        evidence_reference_ids: tuple[str, ...],
    ) -> tuple[_ExecutedNode, ...]:
        """Preserve every malformed model attempt, then admit only a schema-valid retry."""

        attempts: list[_ExecutedNode] = []
        validation_feedback = None
        for attempt in range(1, node.retry_limit + 2):
            current_prompt = _retry_prompt(role_prompt, validation_feedback)
            contract = MicroAgentContract(
                node=node,
                role_prompt=current_prompt,
                output_schema=node.output_schema,
                evaluator=_AcceptingEvaluator(),
            )
            context_pack = build_context_pack(
                node,
                node_instruction=current_prompt,
                constitution=constitution,
                prior_artifacts=prior_artifacts,
                context_records=context_records,
            )
            model_request = compile_micro_agent_request(contract, context_pack)
            response = generate(model_request)
            validation = validate_micro_agent_response(contract, response.text)
            if not validation.accepted:
                attempts.append(
                    self._record_rejected_model_node(
                        node=node,
                        attempt=attempt,
                        input_material=context_pack.to_payload(),
                        prompt_hash=_required_prompt_hash(model_request),
                        response=response,
                        validation_errors=validation.validation_errors,
                    )
                )
                validation_feedback = _validation_feedback(validation)
                continue
            artifact = require_valid_node_output(validation)
            attempts.append(
                self._record_node(
                    run_id=run_id,
                    node=node,
                    attempt=attempt,
                    input_material=context_pack.to_payload(),
                    prompt_hash=_required_prompt_hash(model_request),
                    artifact=artifact,
                    constitution=constitution,
                    evidence_reference_ids=evidence_reference_ids,
                    provider_response=response,
                    validation=validation,
                )
            )
            return tuple(attempts)
        return tuple(attempts)

    def _execute_repair_node(
        self,
        *,
        run_id: RunId,
        node: WorkNode,
        constitution: TaskConstitution,
        draft_node: _ExecutedNode,
        relevant_evidence: tuple[ContextReference, ...],
        generate: Callable[[ModelRequest], ModelResponse],
    ) -> _ExecutedNode:
        from axia.formation.repair import form_repair_context
        from axia.operation.repair_context_packer import pack_repair_context

        assert draft_node.result.artifact is not None
        assert draft_node.result.artifact_id is not None
        assert draft_node.result.scorecard is not None
        validation = NodeValidationResult(
            node_id=draft_node.node.node_id,
            artifact=draft_node.result.artifact,
            validation_errors=(),
        )
        score_input = ArtifactScoreInput(
            source_run_id=run_id,
            source_node=draft_node.node,
            source_artifact_id=draft_node.result.artifact_id,
            artifact=draft_node.result.artifact,
            validation=validation,
            rendered_output=_rendered_output(draft_node.result.artifact),
            evidence_reference_ids=(draft_node.result.artifact_id.value,),
            addressed_constraints=_addressed_constraints(draft_node.result.artifact, constitution),
        )
        repair_context = form_repair_context(score_input, draft_node.result.scorecard, relevant_evidence)
        role_prompt = _repair_prompt()
        context_pack = pack_repair_context(node, repair_context, constitution, node_instruction=role_prompt)
        contract = MicroAgentContract(
            node=node,
            role_prompt=role_prompt,
            output_schema=node.output_schema,
            evaluator=_AcceptingEvaluator(),
        )
        model_request = compile_micro_agent_request(contract, context_pack)
        response = generate(model_request)
        repair_validation = validate_micro_agent_response(contract, response.text)
        artifact = require_valid_node_output(repair_validation)
        recorded = self._record_node(
            run_id=run_id,
            node=node,
            attempt=1,
            input_material=context_pack.to_payload(),
            prompt_hash=_required_prompt_hash(model_request),
            artifact=artifact,
            constitution=constitution,
            evidence_reference_ids=tuple(reference.reference_id for reference in relevant_evidence),
            provider_response=response,
            validation=repair_validation,
        )
        if recorded.result.status == "accepted":
            return _ExecutedNode(node=node, result=_with_status(recorded.result, "repaired"))
        return recorded

    def _record_deterministic_node(
        self,
        *,
        run_id: RunId,
        node: WorkNode,
        attempt: int = 1,
        input_material: Mapping[str, object] | object,
        artifact: TypedArtifact,
        constitution: TaskConstitution,
        evidence_reference_ids: tuple[str, ...],
    ) -> _ExecutedNode:
        input_hash = stable_json_hash(input_material)
        return self._record_node(
            run_id=run_id,
            node=node,
            attempt=attempt,
            input_material=input_material,
            prompt_hash=stable_json_hash({"node": node.node_id.value, "input_hash": input_hash, "operation": "deterministic"}),
            artifact=artifact,
            constitution=constitution,
            evidence_reference_ids=evidence_reference_ids,
            provider_response=None,
        )

    def _record_node(
        self,
        *,
        run_id: RunId,
        node: WorkNode,
        attempt: int,
        input_material: Mapping[str, object] | object,
        prompt_hash: str,
        artifact: TypedArtifact,
        constitution: TaskConstitution,
        evidence_reference_ids: tuple[str, ...],
        provider_response: ModelResponse | None,
        validation: NodeValidationResult | None = None,
    ) -> _ExecutedNode:
        artifact_id = ArtifactId.from_value(
            f"artifact_{node.node_id.value.removeprefix('node_')}_{stable_json_hash({'run': run_id.value, 'artifact': artifact.payload})[:16]}"
        )
        node_validation = validation or NodeValidationResult(node_id=node.node_id, artifact=artifact, validation_errors=())
        scorecard = score_artifact(
            ScorecardId.from_value(
                f"scorecard_{node.node_id.value.removeprefix('node_')}_{stable_json_hash({'run': run_id.value, 'artifact': artifact_id.value})[:16]}"
            ),
            constitution,
            ArtifactScoreInput(
                source_run_id=run_id,
                source_node=node,
                source_artifact_id=artifact_id,
                artifact=artifact,
                validation=node_validation,
                rendered_output=_rendered_output(artifact),
                evidence_reference_ids=evidence_reference_ids,
                addressed_constraints=_addressed_constraints(artifact, constitution),
            ),
        )
        status = "accepted" if scorecard.decision == "accept" else "rejected"
        timestamp = self._timestamp()
        return _ExecutedNode(
            node=node,
            result=RunManifestNodeResult(
                node_id=node.node_id,
                attempt=attempt,
                status=status,
                input_hash=stable_json_hash(input_material),
                prompt_hash=prompt_hash,
                artifact_id=artifact_id,
                artifact=artifact,
                validation_errors=node_validation.validation_errors,
                scorecard=scorecard,
                provider_response=(
                    ProviderResponseRecord.from_response(provider_response.text, provider_response.metadata)
                    if provider_response is not None
                    else None
                ),
                started_at=timestamp,
                ended_at=self._timestamp(),
            ),
        )

    def _record_rejected_model_node(
        self,
        *,
        node: WorkNode,
        attempt: int,
        input_material: Mapping[str, object] | object,
        prompt_hash: str,
        response: ModelResponse,
        validation_errors: tuple[ValidationIssue, ...],
    ) -> _ExecutedNode:
        timestamp = self._timestamp()
        return _ExecutedNode(
            node=node,
            result=RunManifestNodeResult(
                node_id=node.node_id,
                attempt=attempt,
                status="rejected",
                input_hash=stable_json_hash(input_material),
                prompt_hash=prompt_hash,
                artifact_id=None,
                artifact=None,
                validation_errors=validation_errors,
                scorecard=None,
                provider_response=ProviderResponseRecord.from_response(response.text, response.metadata),
                started_at=timestamp,
                ended_at=self._timestamp(),
            ),
        )

    def _record_trace_evidence(self, run_id: RunId, results: tuple[RunManifestNodeResult, ...]) -> None:
        assert self._run_store is not None
        for result in results:
            self._run_store.append(
                RunTraceRecord(
                    run_id=run_id,
                    kind="node",
                    record_id=f"{result.node_id.value}:attempt:{result.attempt}",
                    payload=result.to_payload(),
                )
            )
            if result.artifact_id is None or result.artifact is None or result.scorecard is None:
                continue
            self._run_store.append(
                RunTraceRecord(
                    run_id=result.scorecard.source_run_id,
                    kind="artifact",
                    record_id=result.artifact_id.value,
                    payload={"artifact_id": result.artifact_id.value, "payload": dict(result.artifact.payload)},
                )
            )
            self._run_store.append(
                RunTraceRecord(
                    run_id=result.scorecard.source_run_id,
                    kind="scorecard",
                    record_id=result.scorecard.scorecard_id.value,
                    payload=result.scorecard.to_payload(),
                )
            )

    def _persist_failed_run(
        self,
        *,
        run_id: RunId,
        request: RequestRecord,
        mode: str,
        canonical_request: CanonicalRequest,
        constitution: TaskConstitution,
        graph: WorkGraph,
        results: tuple[RunManifestNodeResult, ...],
        model_calls: int,
        started_at: float,
        error: RunExecutionFailure,
    ) -> None:
        """Store the admitted portion of a failed run before its failure reaches the CLI boundary."""

        if self._run_store is None:
            return
        manifest = RunManifest(
            run_id=run_id,
            created_at=self._timestamp(),
            app_version=__version__,
            user_request_hash=request.content_hash,
            model_profile=self._model_profile,
            prompt_hashes={prompt_hash_key(result.node_id, result.attempt): result.prompt_hash for result in results},
            mode=mode,
            status="failed",
            canonical_request=canonical_request,
            constitution=constitution,
            work_graph=graph,
            node_results=results,
            final_answer=None,
            memory_candidates=(),
            metrics={
                "model_calls": model_calls,
                "duration_seconds": round(self._clock() - started_at, 6),
                "failure_kind": error.kind,
            },
        )
        record_run_manifest(manifest, self._run_store)
        self._record_trace_evidence(run_id, results)
        self._run_store.append(
            RunTraceRecord(
                run_id=run_id,
                kind="error",
                record_id=f"error_{error.kind}",
                payload={"kind": error.kind, "message": error.message},
            )
        )
def _artifact_reference(scope: str, result: RunManifestNodeResult) -> ContextReference:
    assert result.artifact_id is not None and result.artifact is not None
    return ContextReference.from_content(
        scope=scope,
        source_type="artifact",
        reference_id=result.artifact_id.value,
        content=result.artifact.payload,
        accepted=result.status in {"accepted", "repaired"},
    )


def _draft_context_reference(result: RunManifestNodeResult) -> ContextReference:
    """Keep a score-rejected draft inspectable as evidence before repair admits it as a failed artifact."""

    if result.status in {"accepted", "repaired"}:
        return _artifact_reference("draft", result)
    assert result.artifact_id is not None and result.artifact is not None
    return ContextReference.from_content(
        scope="draft",
        source_type="evidence",
        reference_id=result.artifact_id.value,
        content=result.artifact.payload,
        accepted=False,
    )


def _deterministic_plan(canonical_request, constitution: TaskConstitution) -> dict[str, object]:
    return {
        "task_mission": constitution.mission,
        "steps": ["Produce the requested deliverable while addressing every declared constraint."],
        "assumptions": [],
        "unresolved_questions": list(canonical_request.unknowns),
        "addressed_constraints": list(constitution.constraints),
    }


def _deterministic_critique(constitution: TaskConstitution) -> dict[str, object]:
    return {
        "task_mission": constitution.mission,
        "strengths": ["Quick mode records structural validation without an additional critique call."],
        "gaps": [],
        "repair_focus": [],
        "addressed_constraints": list(constitution.constraints),
    }


def _plan_prompt() -> str:
    return (
        "Create a compact plan for the declared task. Copy the mission exactly into task_mission, "
        "list concrete steps, preserve unknowns, and copy every declared constraint exactly into addressed_constraints."
    )


def _draft_prompt() -> str:
    return "Write the requested deliverable from the supplied plan. Return a concise answer only."


def _critique_prompt() -> str:
    return (
        "Inspect the supplied draft against the task constitution. Copy the mission exactly into task_mission, "
        "record concrete strengths, gaps, and repair_focus, and copy every declared constraint exactly into addressed_constraints."
    )


def _repair_prompt() -> str:
    return "Repair only the failures named in the supplied repair context. Return a complete revised answer only."


def _retry_prompt(role_prompt: str, validation_feedback: str | None) -> str:
    if validation_feedback is None:
        return role_prompt
    return "\n\n".join(
        (
            role_prompt,
            "PREVIOUS_OUTPUT_REJECTED\n"
            + validation_feedback
            + "\nReturn a new JSON object that matches OUTPUT_SCHEMA exactly. Do not include commentary or markdown.",
        )
    )


def _validation_feedback(validation: NodeValidationResult) -> str:
    return "; ".join(f"{issue.path} {issue.message}" for issue in validation.validation_errors)


def _addressed_constraints(artifact: TypedArtifact, constitution: TaskConstitution) -> tuple[str, ...]:
    value = artifact.payload.get("addressed_constraints")
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return constitution.constraints


def _rendered_output(artifact: TypedArtifact) -> str:
    answer = artifact.payload.get("answer")
    if isinstance(answer, str):
        return answer
    return json.dumps(artifact.payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _artifact_answer(artifact: TypedArtifact) -> str:
    answer = artifact.payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise RunExecutionFailure(kind="run_verified_answer_missing", message="the verified artifact has no usable answer")
    return answer


def _artifact_caveats(artifact: TypedArtifact) -> tuple[str, ...]:
    caveats = artifact.payload.get("unresolved_caveats", [])
    if not isinstance(caveats, list) or any(not isinstance(item, str) or not item.strip() for item in caveats):
        raise RunExecutionFailure(kind="run_verified_caveats_invalid", message="the verified artifact caveats are invalid")
    return tuple(caveats)


def _required_prompt_hash(request: ModelRequest) -> str:
    value = request.metadata.get("prompt_hash")
    if not isinstance(value, str) or not value:
        raise RunExecutionFailure(kind="run_prompt_hash_missing", message="model requests must declare a prompt hash")
    return value


def _require_accepted(result: RunManifestNodeResult, stage: str) -> None:
    if result.status not in {"accepted", "repaired"}:
        decision = result.scorecard.decision if result.scorecard is not None else "unscored"
        raise RunExecutionFailure(
            kind="run_stage_not_accepted",
            message=f"{stage} was rejected by deterministic scorecard policy with decision {decision!r}",
        )


def _with_status(result: RunManifestNodeResult, status: str) -> RunManifestNodeResult:
    return RunManifestNodeResult(
        node_id=result.node_id,
        attempt=result.attempt,
        status=status,
        input_hash=result.input_hash,
        prompt_hash=result.prompt_hash,
        artifact_id=result.artifact_id,
        artifact=result.artifact,
        validation_errors=result.validation_errors,
        scorecard=result.scorecard,
        provider_response=result.provider_response,
        started_at=result.started_at,
        ended_at=result.ended_at,
    )


def _require_time_limit(started_at: float, max_seconds: int, clock: Callable[[], float]) -> None:
    if clock() - started_at > max_seconds:
        raise RunExecutionFailure(
            kind="run_time_limit_exhausted",
            message="the task constitution wall-clock limit was reached",
        )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
