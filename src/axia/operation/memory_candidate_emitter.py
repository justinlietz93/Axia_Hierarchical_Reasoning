from __future__ import annotations

from axia.boundary.ports.memory_candidate_sink import MemoryCandidateSink
from axia.formation.memory_candidate import MemoryCandidate


def emit_memory_candidate(candidate: MemoryCandidate, sink: MemoryCandidateSink | None = None) -> MemoryCandidate:
    """Emit a candidate to an optional external sink without taking memory-policy ownership."""

    if sink is not None:
        sink.emit(candidate)
    return candidate
