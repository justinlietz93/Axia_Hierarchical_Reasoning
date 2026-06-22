from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from axia.formation.export_candidate import ExportCandidate


class ExportCandidateSink(Protocol):
    def emit(self, candidate: ExportCandidate) -> None:
        """Receive an approved export proposal; all curation and dataset policy stay external."""
