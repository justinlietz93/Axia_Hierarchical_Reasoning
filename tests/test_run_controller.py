from __future__ import annotations

import json
import unittest

from axia.boundary.adapters.sqlite_run_store import SQLiteRunStore
from axia.boundary.ports.model_provider import ModelRequest, ModelResponse
from axia.operation import RunController, RunExecutionFailure, project_run_trace, replay_run
from axia.projection import ModelProfileIdentity
from axia.shared.ids import RunId, stable_text_hash


class ScriptedProvider:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        stage = request.metadata.get("stage")
        if stage == "canonical_request":
            payload = {
                "intent": "compare database options",
                "deliverable_type": "technical recommendation",
                "constraints": ["local-first", "practical tradeoffs"],
                "unknowns": ["expected data volume"],
                "risk_flags": ["recommendation changes at larger scale"],
                "output_format": "concise comparison with recommendation",
                "expected_depth": "standard",
                "needed_context": [],
            }
        else:
            node_id = request.metadata["node_id"]
            payload = _node_payload(node_id)
        return ModelResponse(
            text=json.dumps(payload),
            metadata={
                "provider": "scripted",
                "model": "scripted-tiny",
                "request_id": f"request-{len(self.requests)}",
                "response_id": f"response-{len(self.requests)}",
            },
        )


class RetryingProvider(ScriptedProvider):
    def __init__(self) -> None:
        super().__init__()
        self._canonical_attempts = 0
        self._draft_attempts = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        stage = request.metadata.get("stage")
        if stage == "canonical_request":
            self._canonical_attempts += 1
            if self._canonical_attempts == 1:
                self.requests.append(request)
                return ModelResponse(text='{"intent":"compare database options"}', metadata=_metadata(len(self.requests)))
        if request.metadata.get("node_id") == "node_draft":
            self._draft_attempts += 1
            if self._draft_attempts == 1:
                self.requests.append(request)
                return ModelResponse(text='{"not_answer":"missing the declared answer"}', metadata=_metadata(len(self.requests)))
        return super().generate(request)


def _metadata(index: int) -> dict[str, str]:
    return {
        "provider": "scripted",
        "model": "scripted-tiny",
        "request_id": f"request-{index}",
        "response_id": f"response-{index}",
    }


class ShortDraftProvider(ScriptedProvider):
    def generate(self, request: ModelRequest) -> ModelResponse:
        if request.metadata.get("node_id") == "node_draft":
            self.requests.append(request)
            return ModelResponse(
                text='{"answer":"too short"}',
                metadata=_metadata(len(self.requests)),
            )
        return super().generate(request)


class InvalidCanonicalProvider(ScriptedProvider):
    def __init__(self) -> None:
        super().__init__()
        self._canonical_attempts = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        if request.metadata.get("stage") == "canonical_request":
            self._canonical_attempts += 1
            self.requests.append(request)
            return ModelResponse(text='{"unsupported":true}', metadata=_metadata(len(self.requests)))
        return super().generate(request)


def _node_payload(node_id: str) -> dict[str, object]:
    if node_id == "node_plan":
        return {
            "task_mission": "compare database options",
            "steps": ["Compare local deployment complexity and growth limits."],
            "assumptions": ["The first deployment is single-user."],
            "unresolved_questions": ["expected data volume"],
            "addressed_constraints": ["local-first", "practical tradeoffs"],
        }
    if node_id == "node_draft":
        return {
            "answer": "Compare database options: SQLite is the practical local-first default because it is embedded, simple to operate, and sufficient until data volume or multi-user writes justify PostgreSQL.",
        }
    if node_id == "node_critique":
        return {
            "task_mission": "compare database options",
            "strengths": ["The draft gives a local-first recommendation and a clear scale boundary."],
            "gaps": [],
            "repair_focus": [],
            "addressed_constraints": ["local-first", "practical tradeoffs"],
        }
    raise AssertionError(f"unexpected model node {node_id}")


class RunControllerTests(unittest.TestCase):
    def test_standard_run_forms_complete_replayable_trace_and_persists_it_before_returning(self) -> None:
        provider = ScriptedProvider()
        store = SQLiteRunStore(":memory:")
        controller = RunController(
            provider,
            ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test-profile"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
            run_store=store,
            run_id_factory=lambda: RunId.from_value("run_controller_test"),
            clock=lambda: 0.0,
            timestamp=lambda: "2026-06-21T00:00:00Z",
        )

        execution = controller.execute("Compare database options for a local-first AI tool.", mode="standard")
        stored = store.read_run(execution.manifest.run_id)
        replay = replay_run(execution.manifest.run_id, store)

        self.assertEqual(execution.manifest.status, "complete")
        self.assertEqual(len(execution.manifest.node_results), 10)
        self.assertEqual(len(provider.requests), 4)
        self.assertEqual(stored.manifest.payload, execution.manifest.to_payload())
        self.assertEqual(replay.final_answer, execution.final_answer_text)
        self.assertTrue(execution.final_answer_text.startswith("Compare database options: SQLite is the practical local-first default"))
        self.assertEqual(len(stored.records), 30)

    def test_quick_run_skips_optional_planning_and_critique_model_calls(self) -> None:
        provider = ScriptedProvider()
        controller = RunController(
            provider,
            ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test-profile"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
            run_id_factory=lambda: RunId.from_value("run_controller_quick"),
            clock=lambda: 0.0,
            timestamp=lambda: "2026-06-21T00:00:00Z",
        )

        execution = controller.execute("Compare database options for a local-first AI tool.", mode="quick")

        self.assertEqual(execution.manifest.metrics["model_calls"], 2)
        self.assertEqual(len(provider.requests), 2)
        self.assertEqual(execution.manifest.mode, "quick")

    def test_preserves_rejected_schema_attempts_and_admits_only_bounded_retries(self) -> None:
        provider = RetryingProvider()
        store = SQLiteRunStore(":memory:")
        controller = RunController(
            provider,
            ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test-profile"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
            run_store=store,
            run_id_factory=lambda: RunId.from_value("run_controller_retry"),
            clock=lambda: 0.0,
            timestamp=lambda: "2026-06-21T00:00:00Z",
        )

        execution = controller.execute("Compare database options for a local-first AI tool.", mode="quick")
        canonical_attempts = [
            result for result in execution.manifest.node_results if result.node_id.value == "node_canonicalize"
        ]
        draft_attempts = [result for result in execution.manifest.node_results if result.node_id.value == "node_draft"]
        replay = replay_run(execution.manifest.run_id, store)

        self.assertEqual([(result.attempt, result.status) for result in canonical_attempts], [(1, "rejected"), (2, "accepted")])
        self.assertEqual([(result.attempt, result.status) for result in draft_attempts], [(1, "rejected"), (2, "accepted")])
        self.assertEqual(execution.manifest.metrics["model_calls"], 4)
        self.assertEqual(len(store.read_run(execution.manifest.run_id).records), 32)
        self.assertEqual(replay.final_answer, execution.final_answer_text)

    def test_persists_a_failed_run_after_a_post_constitution_policy_rejection(self) -> None:
        provider = ShortDraftProvider()
        store = SQLiteRunStore(":memory:")
        controller = RunController(
            provider,
            ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test-profile"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
            run_store=store,
            run_id_factory=lambda: RunId.from_value("run_controller_failed"),
            clock=lambda: 0.0,
            timestamp=lambda: "2026-06-21T00:00:00Z",
        )

        with self.assertRaises(RunExecutionFailure) as failure:
            controller.execute("Compare database options for a local-first AI tool.", mode="quick")

        stored = store.read_run(RunId.from_value("run_controller_failed"))
        replay = replay_run(RunId.from_value("run_controller_failed"), store)
        trace = project_run_trace(RunId.from_value("run_controller_failed"), store)

        self.assertEqual(failure.exception.kind, "run_stage_not_accepted")
        self.assertIn("run_controller_failed", failure.exception.message)
        self.assertEqual(stored.manifest.status, "failed")
        self.assertEqual(stored.manifest.payload["final_answer"], None)
        self.assertEqual(replay.final_answer, None)
        self.assertEqual(stored.records[-1].kind, "error")
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.errors[0]["kind"], "run_stage_not_accepted")

    def test_uses_a_declared_raw_request_fallback_after_bounded_intake_rejection(self) -> None:
        provider = InvalidCanonicalProvider()
        controller = RunController(
            provider,
            ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test-profile"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
            run_id_factory=lambda: RunId.from_value("run_controller_fallback"),
            clock=lambda: 0.0,
            timestamp=lambda: "2026-06-21T00:00:00Z",
        )

        execution = controller.execute("Compare database options for a local-first AI tool.", mode="quick")
        canonical_attempts = [
            result for result in execution.manifest.node_results if result.node_id.value == "node_canonicalize"
        ]

        self.assertEqual([(result.attempt, result.status) for result in canonical_attempts], [(1, "rejected"), (2, "rejected"), (3, "accepted")])
        self.assertEqual(execution.manifest.canonical_request.intent, "Compare database options for a local-first AI tool.")
        self.assertTrue(execution.manifest.metrics["canonicalization_fallback"])
        self.assertIsNone(canonical_attempts[-1].provider_response)


if __name__ == "__main__":
    unittest.main()
