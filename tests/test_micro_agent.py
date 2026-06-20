from __future__ import annotations

import unittest

from axia.boundary.adapters.fake_provider import FakeProvider
from axia.boundary.ports.model_provider import ModelRequest, ModelResponse
from axia.formation import (
    MicroAgentContract,
    MicroAgentEvaluation,
    MicroAgentFailure,
    ScorePolicy,
    TypedArtifact,
    WorkNode,
)
from axia.operation import compile_micro_agent_request, execute_micro_agent
from axia.shared.ids import NodeId


OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "value"],
    "properties": {
        "status": {"type": "string"},
        "value": {"type": "string"},
    },
}


class AcceptingEvaluator:
    def __init__(self) -> None:
        self.artifacts: list[TypedArtifact] = []

    def evaluate(self, artifact: TypedArtifact) -> MicroAgentEvaluation:
        self.artifacts.append(artifact)
        return MicroAgentEvaluation(accepted=True, reasons=("schema is valid",))


class RecordingProvider:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(text=self.response_text, metadata={"provider": "recording"})


def _contract(evaluator: AcceptingEvaluator | None = None) -> MicroAgentContract:
    return MicroAgentContract(
        node=WorkNode(
            node_id=NodeId.from_value("node_draft"),
            kind="draft",
            depends_on=(),
            input_schema={"type": "object", "required": ["plan"]},
            output_schema=OUTPUT_SCHEMA,
            context_scope=("plan",),
            allowed_operations=(),
            retry_limit=0,
            score_policy=ScorePolicy(accept_threshold=0.82, repair_threshold=0.65),
            failure_behavior="fail_run",
        ),
        role_prompt="You are the draft writer. Produce one concise answer from the supplied plan.",
        output_schema=OUTPUT_SCHEMA,
        evaluator=evaluator or AcceptingEvaluator(),
    )


class MicroAgentTests(unittest.TestCase):
    def test_compiles_a_stable_request_from_node_contract_and_explicit_context(self) -> None:
        request = compile_micro_agent_request(_contract(), {"plan": "compare SQLite and DuckDB"})

        self.assertEqual(request.output_schema, OUTPUT_SCHEMA)
        self.assertEqual(request.metadata["stage"], "micro_agent")
        prompt = request.messages[0].content
        self.assertIn("NODE_CONTRACT", prompt)
        self.assertIn('"context_scope":["plan"]', prompt)
        self.assertIn('"plan":"compare SQLite and DuckDB"', prompt)

    def test_rejects_context_outside_the_node_scope(self) -> None:
        with self.assertRaises(MicroAgentFailure) as failure:
            compile_micro_agent_request(
                _contract(),
                {"plan": "draft", "prior_run": "implicit shared state"},
            )

        self.assertEqual(failure.exception.kind, "micro_agent_context_scope_violation")

    def test_evaluator_receives_only_a_schema_validated_artifact(self) -> None:
        evaluator = AcceptingEvaluator()
        result = execute_micro_agent(
            _contract(evaluator),
            {"plan": "draft"},
            FakeProvider(),
        )

        self.assertEqual(result.artifact.payload, {"status": "ok", "value": "test"})
        self.assertTrue(result.evaluation.accepted)
        self.assertEqual(evaluator.artifacts, [result.artifact])

    def test_malformed_or_schema_mismatched_provider_output_never_reaches_evaluator(self) -> None:
        for response_text, expected_kind in (
            ("{", "micro_agent_output_json_invalid"),
            ('{"unexpected":true}', "micro_agent_output_schema_invalid"),
        ):
            with self.subTest(response_text=response_text):
                evaluator = AcceptingEvaluator()
                provider = RecordingProvider(response_text)
                with self.assertRaises(MicroAgentFailure) as failure:
                    execute_micro_agent(_contract(evaluator), {"plan": "draft"}, provider)

                self.assertEqual(failure.exception.kind, expected_kind)
                self.assertEqual(evaluator.artifacts, [])
                self.assertEqual(len(provider.requests), 1)


if __name__ == "__main__":
    unittest.main()
