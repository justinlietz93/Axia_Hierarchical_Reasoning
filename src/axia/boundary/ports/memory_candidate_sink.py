from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from axia.formation.memory_candidate import MemoryCandidate


class MemoryCandidateSink(Protocol):
    """Optional external receiver for trace-derived memory candidates."""

    def emit(self, candidate: MemoryCandidate) -> None:
        """Receive a projection; persistence and all memory policy remain external."""
