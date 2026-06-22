from __future__ import annotations

from typing import Mapping


def project_web_run(manifest: Mapping[str, object]) -> dict[str, object]:
    """Return the local web UI's safe read model from one saved manifest."""

    node_results = _objects(manifest.get("node_results"))
    return {
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "mode": manifest.get("mode"),
        "completed_nodes": [
            {"node_id": result.get("node_id"), "status": result.get("status"), "attempt": result.get("attempt")}
            for result in node_results
        ],
        "scorecards": [
            {"node_id": result.get("node_id"), "overall": score.get("overall"), "decision": score.get("decision")}
            for result in node_results
            if isinstance((score := result.get("scorecard")), Mapping)
        ],
        "accepted_artifacts": [
            {"node_id": result.get("node_id"), "artifact_id": result.get("artifact_id"), "artifact": result.get("artifact")}
            for result in node_results
            if result.get("status") in {"accepted", "repaired"} and result.get("artifact") is not None
        ],
        "final_answer": manifest.get("final_answer"),
        "memory_candidates": list(manifest.get("memory_candidates", [])),
    }


def _objects(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))
