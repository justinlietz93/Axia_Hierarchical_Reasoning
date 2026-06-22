from __future__ import annotations

from dataclasses import replace
import json
import unittest

from axia.formation import FinalSynthesisFailure, TypedArtifact
from axia.operation import (
    compile_final_synthesis_request,
    form_final_synthesis_context,
    parse_final_synthesis_response,
)
from axia.projection import RunManifestNodeResult, prompt_hash_key
from axia.shared.ids import ArtifactId, NodeId, stable_text_hash
from axia.source import ProviderResponseRecord
from tests.test_run_manifest import _manifest


class FinalSynthesisTests(unittest.TestCase):
    def test_synthesizes_only_trace_supported_claims_with_requested_output_context(self) -> None:
        manifest = _manifest()
        context = form_final_synthesis_context(
            manifest,
            unresolved_caveats=("Expected scale may change the database choice.",),
            style_constraints=("Keep the comparison concise.",),
        )
        artifact = context.accepted_artifacts[0]
        supported_text = artifact.artifact.payload["answer"]
        assert isinstance(supported_text, str)
        answer = parse_final_synthesis_response(
            context,
            json.dumps(
                {
                    "claims": [
                        {
                            "text": supported_text,
                            "source_artifact_id": artifact.artifact_id.value,
                            "evidence_excerpt": "SQLite is a practical local-first default",
                        }
                    ],
                    "unresolved_caveats": ["Expected scale may change the database choice."],
                }
            ),
        )
        request = compile_final_synthesis_request(context)

        self.assertEqual(answer.render(), supported_text + "\n\nCaveats:\n- Expected scale may change the database choice.")
        self.assertEqual(answer.claims[0].source_artifact_id, artifact.artifact_id)
        self.assertIn('"requested_format":"concise recommendation"', request.messages[0].content)
        self.assertIn('"style_constraints":["Keep the comparison concise."]', request.messages[0].content)

    def test_rejects_claims_from_rejected_artifacts_and_unsupported_new_claims(self) -> None:
        manifest = _manifest()
        rejected_node_id = NodeId.from_value("node_critique")
        rejected_artifact_id = ArtifactId.from_value("artifact_rejected")
        rejected = RunManifestNodeResult(
            node_id=rejected_node_id,
            attempt=1,
            status="rejected",
            input_hash=stable_text_hash("critique context"),
            prompt_hash=stable_text_hash("critique prompt"),
            artifact_id=rejected_artifact_id,
            artifact=TypedArtifact.from_payload({"answer": "Use PostgreSQL for every deployment."}),
            validation_errors=(),
            scorecard=None,
            provider_response=ProviderResponseRecord.from_response('{"answer":"Use PostgreSQL for every deployment."}'),
            started_at="2026-06-20T00:00:01Z",
            ended_at="2026-06-20T00:00:02Z",
        )
        manifest = replace(
            manifest,
            node_results=(*manifest.node_results, rejected),
            prompt_hashes={
                **manifest.prompt_hashes,
                prompt_hash_key(rejected_node_id, 1): rejected.prompt_hash,
            },
        )
        context = form_final_synthesis_context(manifest)
        accepted_artifact = context.accepted_artifacts[0]

        with self.assertRaises(FinalSynthesisFailure) as rejected_failure:
            parse_final_synthesis_response(
                context,
                json.dumps(
                    {
                        "claims": [
                            {
                                "text": "Use PostgreSQL for every deployment.",
                                "source_artifact_id": rejected_artifact_id.value,
                                "evidence_excerpt": "Use PostgreSQL",
                            }
                        ],
                        "unresolved_caveats": [],
                    }
                ),
            )

        with self.assertRaises(FinalSynthesisFailure) as unsupported_failure:
            parse_final_synthesis_response(
                context,
                json.dumps(
                    {
                        "claims": [
                            {
                                "text": "PostgreSQL is the right default.",
                                "source_artifact_id": accepted_artifact.artifact_id.value,
                                "evidence_excerpt": "SQLite is a practical local-first default",
                            }
                        ],
                        "unresolved_caveats": [],
                    }
                ),
            )

        self.assertEqual(rejected_failure.exception.kind, "final_synthesis_rejected_artifact")
        self.assertEqual(unsupported_failure.exception.kind, "final_synthesis_unsupported_claim")


if __name__ == "__main__":
    unittest.main()
