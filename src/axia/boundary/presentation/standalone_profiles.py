from __future__ import annotations

import os
from pathlib import Path
import tomllib

from axia.policy.model_profile import ModelProfile, ModelProfileFailure


def load_standalone_profiles(profile_directory: Path | None = None) -> dict[str, ModelProfile]:
    """Load the built-in local profile plus explicit TOML overrides from one directory."""

    profiles = {"tiny-default": _builtin_tiny_default()}
    directory = profile_directory or Path(os.environ.get("AXIA_PROFILE_DIR", ".axia/profiles"))
    if not directory.exists():
        return profiles
    if not directory.is_dir():
        raise ModelProfileFailure(
            kind="model_profile_directory_invalid",
            message=f"profile path is not a directory: {directory}",
        )
    for path in sorted(directory.glob("*.toml")):
        try:
            loaded = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ModelProfileFailure(
                kind="model_profile_file_invalid",
                message=f"cannot load profile {path}",
            ) from error
        if not isinstance(loaded, dict):
            raise ModelProfileFailure(
                kind="model_profile_file_invalid",
                message=f"profile {path} must be a TOML table",
            )
        profile = ModelProfile.from_payload(loaded)
        profiles[profile.name] = profile
    return dict(sorted(profiles.items()))


def require_standalone_profile(name: str, profile_directory: Path | None = None) -> ModelProfile:
    """Select one named standalone profile without allowing an implicit provider fallback."""

    profiles = load_standalone_profiles(profile_directory)
    try:
        return profiles[name]
    except KeyError as error:
        raise ModelProfileFailure(
            kind="model_profile_not_found",
            message=f"unknown model profile {name!r}; available profiles: {', '.join(profiles)}",
        ) from error


def _builtin_tiny_default() -> ModelProfile:
    return ModelProfile(
        name="tiny-default",
        provider="ollama",
        model=os.environ.get("AXIA_OLLAMA_MODEL", "qwen3:0.6b"),
        host=os.environ.get("AXIA_OLLAMA_HOST", "http://localhost:11434"),
        context_window_tokens=4096,
        max_output_tokens=512,
        temperature=0.0,
        top_p=1.0,
        top_k=1,
        repeat_penalty=1.0,
        seed=1729,
        json_mode="preferred",
        timeout_seconds=90,
        retry_attempts=2,
    )
