from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, ClassVar
from uuid import uuid4


def stable_json_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for JSON-serializable material."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StableId:
    prefix: ClassVar[str] = "id"

    value: str

    @classmethod
    def new(cls) -> StableId:
        return cls(f"{cls.prefix}_{uuid4().hex}")

    @classmethod
    def from_value(cls, value: str) -> StableId:
        if not value.startswith(f"{cls.prefix}_"):
            raise ValueError(f"{cls.__name__} must start with {cls.prefix}_")
        return cls(value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RunId(StableId):
    prefix: ClassVar[str] = "run"


@dataclass(frozen=True)
class NodeId(StableId):
    prefix: ClassVar[str] = "node"


@dataclass(frozen=True)
class ArtifactId(StableId):
    prefix: ClassVar[str] = "artifact"

