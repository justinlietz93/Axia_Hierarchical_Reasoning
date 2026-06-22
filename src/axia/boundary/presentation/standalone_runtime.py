from __future__ import annotations

import os
from dataclasses import dataclass

from axia.boundary.adapters.crux_provider import CruxProviderAdapter
from axia.boundary.ports.model_provider import ModelProvider
from axia.policy.model_profile import ModelProfile, ModelProfileFailure
from axia.projection.run_manifest import ModelProfileIdentity


@dataclass(frozen=True)
class StandaloneRuntime:
    """The standalone composition result; hosts may instead inject their own provider."""

    provider: ModelProvider
    profile: ModelProfile
    profile_identity: ModelProfileIdentity


def compose_standalone_runtime(profile: ModelProfile) -> StandaloneRuntime:
    """Bind one standalone local profile to the optional Crux provider boundary."""

    if profile.provider != "ollama":
        raise ModelProfileFailure(
            kind="standalone_profile_provider_unsupported",
            message="the standalone runtime currently composes only ollama profiles through Crux",
        )
    os.environ.setdefault("PT_TIMEOUT_START_SECONDS", str(profile.timeout_seconds))
    provider = CruxProviderAdapter.from_crux_factory(
        provider_name=profile.provider,
        model=profile.model,
        host=profile.host,
    )
    return StandaloneRuntime(
        provider=provider,
        profile=profile,
        profile_identity=ModelProfileIdentity(
            name=profile.name,
            profile_hash=profile.profile_hash(),
            provider_metadata={"provider": profile.provider, "model": profile.model, "host": profile.host},
        ),
    )
