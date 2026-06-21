from __future__ import annotations

import json
from pathlib import Path

from axia.benchmark.report import BenchmarkReport


class JsonBenchmarkReportStore:
    """Local JSON report writer for inspectable benchmark comparison evidence."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def write(self, report: BenchmarkReport) -> Path:
        self._directory.mkdir(parents=True, exist_ok=True)
        destination = self._directory / f"{report.suite.suite_id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(report.to_payload(), ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination
