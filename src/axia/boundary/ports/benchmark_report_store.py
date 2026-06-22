from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from axia.benchmark.report import BenchmarkReport


class BenchmarkReportStore(Protocol):
    """Persist a complete local benchmark report without defining benchmark semantics."""

    def write(self, report: BenchmarkReport) -> Path:
        """Store one versioned report and return its local path."""
