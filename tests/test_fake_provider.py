import unittest

from axia.boundary.adapters.fake_provider import FakeProvider, fake_provider_from_config
from axia.boundary.ports.model_provider import ModelMessage, ModelRequest, ProviderFailure


class FakeProviderTests(unittest.TestCase):
    def test_valid_schema_response_is_deterministic(self) -> None:
        provider = FakeProvider()
        request = ModelRequest(
            messages=[ModelMessage(role="user", content="return output_schema")],
            output_schema={"type": "object"},
        )

        response = provider.generate(request)

        self.assertEqual(response.text, '{"status": "ok", "value": "test"}')
        self.assertEqual(response.metadata["request_id"], "fake-123")
        self.assertEqual(response.metadata["response_id"], "fake-456")

    def test_malformed_json_mode(self) -> None:
        provider = FakeProvider(mode="malformed_json")
        response = provider.generate(ModelRequest(messages=[]))
        self.assertEqual(response.text, "{")

    def test_timeout_mode_raises_retryable_failure(self) -> None:
        provider = FakeProvider(mode="timeout")
        with self.assertRaises(ProviderFailure) as failure:
            provider.generate(ModelRequest(messages=[]))
        self.assertTrue(failure.exception.retryable)

    def test_config_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            fake_provider_from_config({"mode": "random"})


if __name__ == "__main__":
    unittest.main()

