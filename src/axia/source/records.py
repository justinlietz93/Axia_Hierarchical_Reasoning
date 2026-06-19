from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from axia.shared.ids import ArtifactId, RunId, stable_json_hash, stable_text_hash


@dataclass(frozen=True)
class RequestRecord:
    raw_text: str
    content_hash: str

    @classmethod
    def from_text(cls, raw_text: str) -> RequestRecord:
        return cls(raw_text=raw_text, content_hash=stable_text_hash(raw_text))


@dataclass(frozen=True)
class ProviderResponseRecord:
    text: str
    metadata: Mapping[str, str]
    content_hash: str

    @classmethod
    def from_response(
        cls,
        text: str,
        metadata: Mapping[str, str] | None = None,
    ) -> ProviderResponseRecord:
        metadata = dict(metadata or {})
        content_hash = stable_json_hash({"text": text, "metadata": metadata})
        return cls(text=text, metadata=metadata, content_hash=content_hash)


@dataclass(frozen=True)
class ArtifactLineage:
    artifact_id: ArtifactId
    run_id: RunId
    source_hashes: tuple[str, ...]

    @classmethod
    def from_sources(
        cls,
        artifact_id: ArtifactId,
        run_id: RunId,
        source_hashes: tuple[str, ...],
    ) -> ArtifactLineage:
        if not source_hashes:
            raise ValueError("artifact lineage requires at least one source hash")
        return cls(artifact_id=artifact_id, run_id=run_id, source_hashes=source_hashes)

