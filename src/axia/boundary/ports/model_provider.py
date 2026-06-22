from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from axia.shared.errors import AxiaError


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[ModelMessage]
    output_schema: Mapping[str, object] | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def prompt_text(self) -> str:
        return "\n".join(f"{message.role}: {message.content}" for message in self.messages)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class ProviderFailure(AxiaError):
    retryable: bool = False


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a model response through a boundary provider."""

