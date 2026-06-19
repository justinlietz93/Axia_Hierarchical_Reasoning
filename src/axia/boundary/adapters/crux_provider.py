from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Mapping, Protocol

from axia.boundary.ports.model_provider import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderFailure,
)


class CruxChatProvider(Protocol):
    """The narrow portion of a Crux provider used by Axia's boundary adapter."""

    def chat(self, request: object) -> object:
        """Return a normalized Crux chat response."""


@dataclass(frozen=True)
class CruxImportSurface:
    """Pinned optional Crux symbols used only by the boundary adapter."""

    chat_request: type
    chat_response: type
    message: type
    model_info: type
    model_registry_repository: type
    model_registry_snapshot: type
    provider_factory: type
    provider_metadata: type
    adapter_params: type
    llm_provider: type
    model_listing_provider: type


def load_crux_import_surface() -> CruxImportSurface:
    """Load the optional Crux API surface without leaking it into Axia core."""

    try:
        base = import_module("crux_providers.base")
        adapter_params = import_module("crux_providers.base.dto.adapter_params")
        interfaces = import_module("crux_providers.base.interfaces")
    except ImportError as error:
        raise ProviderFailure(
            kind="crux_unavailable",
            message="The optional Crux adapter requires 'axia[crux]'.",
        ) from error

    required = {
        "chat_request": (base, "ChatRequest"),
        "chat_response": (base, "ChatResponse"),
        "message": (base, "Message"),
        "model_info": (base, "ModelInfo"),
        "model_registry_repository": (base, "ModelRegistryRepository"),
        "model_registry_snapshot": (base, "ModelRegistrySnapshot"),
        "provider_factory": (base, "ProviderFactory"),
        "provider_metadata": (base, "ProviderMetadata"),
        "adapter_params": (adapter_params, "AdapterParams"),
        "llm_provider": (interfaces, "LLMProvider"),
        "model_listing_provider": (interfaces, "ModelListingProvider"),
    }
    missing = [name for name, (module, attribute) in required.items() if not hasattr(module, attribute)]
    if missing:
        raise ProviderFailure(
            kind="crux_import_surface_invalid",
            message=f"Crux is missing required public symbols: {', '.join(sorted(missing))}.",
        )

    return CruxImportSurface(
        **{name: getattr(module, attribute) for name, (module, attribute) in required.items()}
    )


@dataclass(frozen=True)
class CruxProviderAdapter:
    """Translate Axia-native model calls through an injected Crux provider."""

    provider: CruxChatProvider
    model: str
    import_surface: CruxImportSurface

    @classmethod
    def from_crux_factory(
        cls,
        *,
        provider_name: str,
        model: str,
        adapter_params: object | None = None,
        **provider_kwargs: object,
    ) -> "CruxProviderAdapter":
        """Build an adapter at a composition root when Axia owns no provider instance."""

        import_surface = load_crux_import_surface()
        provider = import_surface.provider_factory.create(
            provider_name,
            params=adapter_params,
            **provider_kwargs,
        )
        return cls(provider=provider, model=model, import_surface=import_surface)

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Translate an Axia request and response across the Crux boundary."""

        crux_request = self._to_crux_request(request)
        try:
            crux_response = self.provider.chat(crux_request)
        except Exception as error:
            raise self._to_provider_failure(error) from error

        metadata = self._to_axia_metadata(getattr(crux_response, "meta", None))
        error_message = metadata.get("provider_error")
        if error_message:
            raise ProviderFailure(
                kind=metadata.get("provider_error_kind", "provider_error"),
                message=error_message,
                retryable=metadata.get("retryable") == "true",
            )

        return ModelResponse(text=getattr(crux_response, "text", None) or "", metadata=metadata)

    def _to_crux_request(self, request: ModelRequest) -> object:
        messages = [self._to_crux_message(message) for message in request.messages]
        return self.import_surface.chat_request(
            model=self.model,
            messages=messages,
            response_format="json_object" if request.output_schema is not None else None,
            json_schema=dict(request.output_schema) if request.output_schema is not None else None,
            extra={"axia_metadata": dict(request.metadata)},
        )

    def _to_crux_message(self, message: ModelMessage) -> object:
        return self.import_surface.message(role=message.role, content=message.content)

    def _to_axia_metadata(self, crux_metadata: object | None) -> Mapping[str, str]:
        if crux_metadata is None:
            return {"provider": "crux", "model": self.model}

        values = _metadata_values(crux_metadata)
        metadata = {
            "provider": _as_text(values.get("provider_name"), "crux"),
            "model": _as_text(values.get("model_name"), self.model),
        }
        for source, target in (
            ("request_id", "request_id"),
            ("response_id", "response_id"),
            ("http_status", "http_status"),
            ("latency_ms", "latency_ms"),
        ):
            value = values.get(source)
            if value is not None:
                metadata[target] = _as_text(value, "")

        extra = values.get("extra")
        if isinstance(extra, Mapping) and extra.get("error"):
            metadata["provider_error"] = _as_text(extra["error"], "provider failure")
            kind = _as_text(extra.get("code"), "provider_error")
            metadata["provider_error_kind"] = kind
            if kind in {"rate_limit", "timeout", "transient", "unavailable", "server_error"}:
                metadata["retryable"] = "true"
        return metadata

    def _to_provider_failure(self, error: Exception) -> ProviderFailure:
        kind = _as_text(getattr(error, "code", None), "provider_error")
        return ProviderFailure(
            kind=kind,
            message=_as_text(getattr(error, "message", None), str(error)),
            retryable=bool(getattr(error, "retryable", False)),
        )


def _metadata_values(metadata: object) -> Mapping[str, object]:
    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        values = to_dict()
        if isinstance(values, Mapping):
            return values
    values = getattr(metadata, "__dict__", None)
    return values if isinstance(values, Mapping) else {}


def _as_text(value: object | None, default: str) -> str:
    if value is None:
        return default
    raw_value = getattr(value, "value", value)
    return str(raw_value)
