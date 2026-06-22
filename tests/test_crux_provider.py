from __future__ import annotations

from dataclasses import dataclass, field
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from axia.boundary.adapters.crux_provider import (
    CruxImportSurface,
    CruxProviderAdapter,
    load_crux_import_surface,
)
from axia.boundary.ports.model_provider import ModelMessage, ModelRequest, ProviderFailure


@dataclass
class StubMessage:
    role: str
    content: str


@dataclass
class StubChatRequest:
    model: str
    messages: list[StubMessage]
    response_format: str | None = None
    json_schema: dict[str, object] | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class StubMetadata:
    provider_name: str = "ollama"
    model_name: str = "tiny-model"
    request_id: str | None = "request-1"
    response_id: str | None = "response-1"
    http_status: int | None = 200
    latency_ms: float | None = 4.5
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass
class StubChatResponse:
    text: str | None
    meta: StubMetadata


class StubProvider:
    def __init__(self, response: StubChatResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.request: StubChatRequest | None = None

    def chat(self, request: StubChatRequest) -> StubChatResponse:
        self.request = request
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


class StubFactory:
    created: list[tuple[str, object | None, dict[str, object]]] = []
    provider: StubProvider | None = None

    @classmethod
    def create(cls, provider_name: str, *, params: object | None = None, **kwargs: object) -> StubProvider:
        cls.created.append((provider_name, params, kwargs))
        assert cls.provider is not None
        return cls.provider


class RetryableCruxError(Exception):
    code = "timeout"
    message = "timed out"
    retryable = True


def _import_surface() -> CruxImportSurface:
    return CruxImportSurface(
        chat_request=StubChatRequest,
        chat_response=StubChatResponse,
        message=StubMessage,
        model_info=object,
        model_registry_repository=object,
        model_registry_snapshot=object,
        provider_factory=StubFactory,
        provider_metadata=StubMetadata,
        adapter_params=object,
        llm_provider=object,
        model_listing_provider=object,
    )


class CruxProviderAdapterTests(unittest.TestCase):
    def test_translates_native_request_and_crux_response(self) -> None:
        provider = StubProvider(StubChatResponse(text="result", meta=StubMetadata()))
        adapter = CruxProviderAdapter(provider=provider, model="tiny-model", import_surface=_import_surface())

        response = adapter.generate(
            ModelRequest(
                messages=[ModelMessage(role="system", content="be precise"), ModelMessage(role="user", content="solve")],
                output_schema={"type": "object"},
                metadata={"run_id": "run-1"},
            )
        )

        assert provider.request is not None
        self.assertEqual(provider.request.model, "tiny-model")
        self.assertEqual(provider.request.response_format, "json_object")
        self.assertEqual(provider.request.json_schema, {"type": "object"})
        self.assertEqual(provider.request.extra, {"axia_metadata": {"run_id": "run-1"}})
        self.assertEqual([(message.role, message.content) for message in provider.request.messages], [("system", "be precise"), ("user", "solve")])
        self.assertEqual(response.text, "result")
        self.assertEqual(response.metadata["provider"], "ollama")
        self.assertEqual(response.metadata["request_id"], "request-1")

    def test_translates_crux_exception_to_native_failure(self) -> None:
        adapter = CruxProviderAdapter(
            provider=StubProvider(error=RetryableCruxError()),
            model="tiny-model",
            import_surface=_import_surface(),
        )

        with self.assertRaises(ProviderFailure) as failure:
            adapter.generate(ModelRequest(messages=[]))

        self.assertEqual(failure.exception.kind, "timeout")
        self.assertEqual(failure.exception.message, "timed out")
        self.assertTrue(failure.exception.retryable)

    def test_translates_crux_error_metadata_to_native_failure(self) -> None:
        provider = StubProvider(
            StubChatResponse(
                text=None,
                meta=StubMetadata(extra={"error": "overloaded", "code": "transient"}),
            )
        )
        adapter = CruxProviderAdapter(provider=provider, model="tiny-model", import_surface=_import_surface())

        with self.assertRaises(ProviderFailure) as failure:
            adapter.generate(ModelRequest(messages=[]))

        self.assertEqual(failure.exception.kind, "transient")
        self.assertTrue(failure.exception.retryable)

    def test_factory_is_used_only_when_the_composition_root_requests_it(self) -> None:
        provider = StubProvider(StubChatResponse(text="result", meta=StubMetadata()))
        StubFactory.provider = provider
        StubFactory.created.clear()

        with patch("axia.boundary.adapters.crux_provider.load_crux_import_surface", return_value=_import_surface()):
            adapter = CruxProviderAdapter.from_crux_factory(
                provider_name="ollama",
                model="tiny-model",
                adapter_params="configured-elsewhere",
                host="http://localhost:11434",
            )

        self.assertIs(adapter.provider, provider)
        self.assertEqual(StubFactory.created, [("ollama", "configured-elsewhere", {"host": "http://localhost:11434"})])

    def test_missing_optional_dependency_is_a_native_failure(self) -> None:
        with patch("axia.boundary.adapters.crux_provider.import_module", side_effect=ImportError("missing")):
            with self.assertRaises(ProviderFailure) as failure:
                load_crux_import_surface()

        self.assertEqual(failure.exception.kind, "crux_unavailable")

    def test_import_smoke_checks_the_declared_optional_surface(self) -> None:
        base = ModuleType("crux_providers.base")
        adapter_params = ModuleType("crux_providers.base.dto.adapter_params")
        interfaces = ModuleType("crux_providers.base.interfaces")
        declared = {
            "ChatRequest": StubChatRequest,
            "ChatResponse": StubChatResponse,
            "Message": StubMessage,
            "ModelInfo": object,
            "ModelRegistryRepository": object,
            "ModelRegistrySnapshot": object,
            "ProviderFactory": StubFactory,
            "ProviderMetadata": StubMetadata,
        }
        for name, value in declared.items():
            setattr(base, name, value)
        adapter_params.AdapterParams = object
        interfaces.LLMProvider = object
        interfaces.ModelListingProvider = object

        with patch.dict(
            sys.modules,
            {
                "crux_providers": ModuleType("crux_providers"),
                "crux_providers.base": base,
                "crux_providers.base.dto": ModuleType("crux_providers.base.dto"),
                "crux_providers.base.dto.adapter_params": adapter_params,
                "crux_providers.base.interfaces": interfaces,
            },
        ):
            surface = load_crux_import_surface()

        self.assertIs(surface.chat_request, StubChatRequest)
        self.assertIs(surface.provider_factory, StubFactory)

    def test_import_smoke_rejects_a_missing_declared_symbol(self) -> None:
        base = ModuleType("crux_providers.base")
        adapter_params = ModuleType("crux_providers.base.dto.adapter_params")
        interfaces = ModuleType("crux_providers.base.interfaces")
        for name, value in {
            "ChatRequest": StubChatRequest,
            "ChatResponse": StubChatResponse,
            "Message": StubMessage,
            "ModelRegistryRepository": object,
            "ModelRegistrySnapshot": object,
            "ProviderFactory": StubFactory,
            "ProviderMetadata": StubMetadata,
        }.items():
            setattr(base, name, value)
        adapter_params.AdapterParams = object
        interfaces.LLMProvider = object
        interfaces.ModelListingProvider = object

        with patch.dict(
            sys.modules,
            {
                "crux_providers": ModuleType("crux_providers"),
                "crux_providers.base": base,
                "crux_providers.base.dto": ModuleType("crux_providers.base.dto"),
                "crux_providers.base.dto.adapter_params": adapter_params,
                "crux_providers.base.interfaces": interfaces,
            },
        ):
            with self.assertRaises(ProviderFailure) as failure:
                load_crux_import_surface()

        self.assertEqual(failure.exception.kind, "crux_import_surface_invalid")


if __name__ == "__main__":
    unittest.main()
