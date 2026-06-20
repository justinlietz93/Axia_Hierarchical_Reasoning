from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from axia.shared.errors import AxiaError
from axia.shared.ids import NodeId, RunId, stable_json_hash


@dataclass(frozen=True)
class ContextQuery:
    """A bounded request for external context during one reasoning run."""

    run_id: RunId
    node_id: NodeId
    scope: str
    query: str
    attempt: int = 1
    max_records: int = 8

    def __post_init__(self) -> None:
        if not self.scope.strip() or not self.query.strip():
            raise ContextProviderFailure(
                kind="context_query_missing_value",
                message="context queries require non-empty scope and query text",
            )
        if self.attempt < 1 or self.max_records < 1:
            raise ContextProviderFailure(
                kind="context_query_invalid_limit",
                message="context query attempt and max_records must be greater than zero",
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id.value,
            "node_id": self.node_id.value,
            "scope": self.scope,
            "query": self.query,
            "attempt": self.attempt,
            "max_records": self.max_records,
        }

    def trace_id(self) -> str:
        return f"context_{stable_json_hash(self.to_payload())}"


@dataclass(frozen=True)
class ContextRecord:
    """One external context result translated into an Axia-native boundary record."""

    reference_id: str
    content: object
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise ContextProviderFailure(
                kind="context_record_missing_identity",
                message="context records require a reference ID",
            )
        try:
            stable_json_hash(self.content)
        except TypeError as error:
            raise ContextProviderFailure(
                kind="context_record_non_json_content",
                message="context records must contain JSON-serializable content",
            ) from error

    @property
    def content_hash(self) -> str:
        return stable_json_hash(self.content)


@dataclass(frozen=True)
class ContextResponse:
    """The provider result for a single scoped context query."""

    records: tuple[ContextRecord, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextProviderFailure(AxiaError):
    """A translated context-provider failure suitable for deterministic policy."""


class ContextProvider(Protocol):
    def retrieve(self, query: ContextQuery) -> ContextResponse:
        """Supply scoped external context without defining Axia's reasoning policy."""
