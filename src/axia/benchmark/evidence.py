from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkDecompositionStep:
    """One typed work step recorded for benchmark decomposition scoring."""

    step_id: str
    purpose: str
    covered_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.step_id.strip() or not self.purpose.strip():
            raise ValueError("benchmark decomposition steps require an ID and purpose")
        if any(not constraint.strip() for constraint in self.covered_constraints):
            raise ValueError("benchmark decomposition constraints must be non-empty")
        if len(set(self.covered_constraints)) != len(self.covered_constraints):
            raise ValueError("benchmark decomposition constraints must be unique per step")

    def to_payload(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "purpose": self.purpose,
            "covered_constraints": list(self.covered_constraints),
        }


@dataclass(frozen=True)
class BenchmarkEvidenceSupport:
    """A traceable link from one final-output claim to one evidence reference."""

    claim_id: str
    evidence_reference_id: str

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.evidence_reference_id.strip():
            raise ValueError("benchmark evidence links require a claim ID and evidence reference ID")

    def to_payload(self) -> dict[str, str]:
        return {"claim_id": self.claim_id, "evidence_reference_id": self.evidence_reference_id}


@dataclass(frozen=True)
class BenchmarkRepairAttempt:
    """Observed score movement for one bounded repair attempt."""

    attempt: int
    before_score: float
    after_score: float
    accepted: bool

    def __post_init__(self) -> None:
        if self.attempt <= 0:
            raise ValueError("benchmark repair attempts start at one")
        for value in (self.before_score, self.after_score):
            if not 0 <= value <= 1:
                raise ValueError("benchmark repair scores must be within [0, 1]")

    def to_payload(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "before_score": self.before_score,
            "after_score": self.after_score,
            "accepted": self.accepted,
        }


@dataclass(frozen=True)
class BenchmarkReplayEvidence:
    """The saved manifest identity and observed result of replaying one run."""

    manifest_hash: str
    replay_succeeded: bool

    def __post_init__(self) -> None:
        if not self.manifest_hash.strip():
            raise ValueError("benchmark replay evidence requires a manifest hash")

    def to_payload(self) -> dict[str, object]:
        return {"manifest_hash": self.manifest_hash, "replay_succeeded": self.replay_succeeded}


@dataclass(frozen=True)
class BenchmarkControlEvidence:
    """Run evidence used to score reasoning controls without inferring them from prose."""

    decomposition_steps: tuple[BenchmarkDecompositionStep, ...] = ()
    schema_valid: bool | None = None
    addressed_constraints: tuple[str, ...] = ()
    output_claim_ids: tuple[str, ...] = ()
    evidence_support: tuple[BenchmarkEvidenceSupport, ...] = ()
    repair_attempts: tuple[BenchmarkRepairAttempt, ...] = ()
    replay: BenchmarkReplayEvidence | None = None

    def __post_init__(self) -> None:
        if self.schema_valid is not None and not isinstance(self.schema_valid, bool):
            raise ValueError("benchmark schema validity must be true, false, or absent")
        for field_name, values in (
            ("addressed_constraints", self.addressed_constraints),
            ("output_claim_ids", self.output_claim_ids),
        ):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError(f"benchmark {field_name} must contain unique non-empty values")
        step_ids = [step.step_id for step in self.decomposition_steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("benchmark decomposition step IDs must be unique")
        repair_attempts = [repair.attempt for repair in self.repair_attempts]
        if len(set(repair_attempts)) != len(repair_attempts):
            raise ValueError("benchmark repair attempts must be unique")
        supported_claim_ids = {support.claim_id for support in self.evidence_support}
        if not supported_claim_ids.issubset(set(self.output_claim_ids)):
            raise ValueError("benchmark evidence support must reference declared output claims")

    def to_payload(self) -> dict[str, object]:
        return {
            "decomposition_steps": [step.to_payload() for step in self.decomposition_steps],
            "schema_valid": self.schema_valid,
            "addressed_constraints": list(self.addressed_constraints),
            "output_claim_ids": list(self.output_claim_ids),
            "evidence_support": [support.to_payload() for support in self.evidence_support],
            "repair_attempts": [repair.to_payload() for repair in self.repair_attempts],
            "replay": self.replay.to_payload() if self.replay is not None else None,
        }
