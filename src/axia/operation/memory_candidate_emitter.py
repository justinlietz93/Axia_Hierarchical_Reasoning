from __future__ import annotations

from axia.formation.memory_candidate import MemoryCandidate


def emit_memory_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    """Return a candidate projection without storage or promotion side effects."""

    return candidate
