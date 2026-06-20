from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.boundary.ports.context_provider import (
    ContextProvider,
    ContextProviderFailure,
    ContextQuery,
    ContextRecord,
)
from axia.boundary.ports.run_store import RunStore, RunTraceRecord, StoredRunTraceRecord
from axia.formation.context_pack import ContextReference


@dataclass(frozen=True)
class ContextRetrieval:
    """The run-local evidence supplied for one optional context query."""

    query: ContextQuery
    evidence: tuple[ContextReference, ...]
    provider_metadata: Mapping[str, str]
    provider_available: bool
    trace_record: StoredRunTraceRecord | None


def retrieve_context(
    query: ContextQuery,
    provider: ContextProvider | None,
    *,
    run_store: RunStore | None = None,
) -> ContextRetrieval:
    """Retrieve optional context as evidence and record its references in the run trace."""

    if provider is None:
        evidence: tuple[ContextReference, ...] = ()
        provider_metadata: Mapping[str, str] = {}
        provider_available = False
    else:
        response = provider.retrieve(query)
        ordered_records = tuple(sorted(response.records, key=lambda record: (record.reference_id, record.content_hash)))
        duplicate_reference_ids = _duplicate_reference_ids(ordered_records)
        if duplicate_reference_ids:
            raise ContextProviderFailure(
                kind="context_provider_duplicate_reference",
                message=f"context provider returned duplicate references: {', '.join(duplicate_reference_ids)}",
            )
        evidence = tuple(
            ContextReference.from_content(
                scope=query.scope,
                source_type="evidence",
                reference_id=record.reference_id,
                content=record.content,
            )
            for record in ordered_records[: query.max_records]
        )
        provider_metadata = dict(response.metadata)
        provider_available = True

    trace_record = None
    if run_store is not None:
        trace_record = run_store.append(
            RunTraceRecord(
                run_id=query.run_id,
                kind="context",
                record_id=query.trace_id(),
                payload={
                    "query": query.to_payload(),
                    "provider_available": provider_available,
                    "provider_metadata": dict(provider_metadata),
                    "result_references": [
                        {
                            "reference_id": reference.reference_id,
                            "content_hash": reference.content_hash,
                        }
                        for reference in evidence
                    ],
                },
            )
        )
    return ContextRetrieval(
        query=query,
        evidence=evidence,
        provider_metadata=provider_metadata,
        provider_available=provider_available,
        trace_record=trace_record,
    )


def _duplicate_reference_ids(records: tuple[ContextRecord, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        reference_id = record.reference_id
        if reference_id in seen:
            duplicates.append(reference_id)
        seen.add(reference_id)
    return tuple(duplicates)
