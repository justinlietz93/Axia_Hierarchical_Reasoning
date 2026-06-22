from dataclasses import dataclass


@dataclass(frozen=True)
class AxiaError(Exception):
    """Base Axia error with a stable kind for trace records."""

    kind: str
    message: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.message}"

