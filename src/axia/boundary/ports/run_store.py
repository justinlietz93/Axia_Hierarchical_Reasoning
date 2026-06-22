from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from axia.shared.errors import AxiaError
from axia.shared.ids import RunId


RUN_TRACE_KINDS = frozenset(
    {
        "node",
        "artifact",
        "scorecard",
        "error",
        "context",
        "memory_candidate",
    }
)


@dataclass(frozen=True)
class RunManifestRecord:
    """The run-scoped envelope required before trace evidence can be stored."""

    run_id: RunId
    created_at: str
    status: str
    mode: str
    request_hash: str
    payload: Mapping[str, object]


@dataclass(frozen=True)
class RunTraceRecord:
    """A typed, run-scoped trace record before storage assigns an order."""

    run_id: RunId
    kind: str
    record_id: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.kind not in RUN_TRACE_KINDS:
            allowed_kinds = ", ".join(sorted(RUN_TRACE_KINDS))
            raise ValueError(f"unsupported run trace kind {self.kind!r}; expected one of {allowed_kinds}")


@dataclass(frozen=True)
class StoredRunTraceRecord(RunTraceRecord):
    """A trace record with its durable order inside one run trace."""

    sequence: int


@dataclass(frozen=True)
class StoredRun:
    """A replayable run envelope and the evidence recorded for that run."""

    manifest: RunManifestRecord
    records: tuple[StoredRunTraceRecord, ...]


@dataclass(frozen=True)
class StoredRunSummary:
    """The small local index record needed to browse stored reasoning runs."""

    run_id: RunId
    created_at: str
    status: str
    mode: str
    request_hash: str


@dataclass(frozen=True)
class RunStoreFailure(AxiaError):
    """A stable run-store failure suitable for trace and caller handling."""


class RunStore(Protocol):
    """Persist and reconstruct evidence for one reasoning run."""

    def create_run(self, manifest: RunManifestRecord) -> None:
        """Create an empty replayable run envelope."""

    def append(self, record: RunTraceRecord) -> StoredRunTraceRecord:
        """Append one typed evidence record to an existing run."""

    def read_run(self, run_id: RunId) -> StoredRun:
        """Load one run and its evidence in the recorded order."""

    def list_runs(self) -> tuple[StoredRunSummary, ...]:
        """List local run envelopes without exposing their stored contents."""
