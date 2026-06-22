from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from axia.boundary.presentation.standalone_profiles import (
    load_standalone_profiles,
    require_standalone_profile,
)
from axia.policy.model_profile import ModelProfile, ModelProfileFailure


def _profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "tiny-test",
        "provider": "ollama",
        "model": "qwen3:0.6b",
        "host": "http://localhost:11434",
        "context_window_tokens": 4096,
        "max_output_tokens": 512,
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
        "repeat_penalty": 1.0,
        "seed": 1729,
        "json_mode": "preferred",
        "timeout_seconds": 90,
        "retry_attempts": 2,
    }
    payload.update(overrides)
    return payload


class ModelProfileTests(unittest.TestCase):
    def test_profile_hash_captures_the_full_reproducible_configuration(self) -> None:
        baseline = ModelProfile.from_payload(_profile_payload())
        changed = ModelProfile.from_payload(_profile_payload(temperature=0.2))

        self.assertNotEqual(baseline.profile_hash(), changed.profile_hash())
        self.assertEqual(baseline.to_payload()["model"], "qwen3:0.6b")

    def test_profile_rejects_missing_or_unknown_values(self) -> None:
        with self.assertRaises(ModelProfileFailure) as missing:
            ModelProfile.from_payload({"name": "tiny"})
        with self.assertRaises(ModelProfileFailure) as unknown:
            ModelProfile.from_payload(_profile_payload(extra="not admitted"))

        self.assertEqual(missing.exception.kind, "model_profile_fields_missing")
        self.assertEqual(unknown.exception.kind, "model_profile_unknown_fields")

    def test_loader_preserves_builtin_and_allows_explicit_named_override(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "tiny-default.toml"
            path.write_text(
                "\n".join(
                    f'{key} = {value!r}'
                    for key, value in _profile_payload(name="tiny-default", model="lfm2.5-thinking:1.2b").items()
                ),
                encoding="utf-8",
            )
            profiles = load_standalone_profiles(Path(temporary_directory))

        self.assertEqual(profiles["tiny-default"].model, "lfm2.5-thinking:1.2b")
        self.assertEqual(require_standalone_profile("tiny-default", Path("missing-directory")).name, "tiny-default")


if __name__ == "__main__":
    unittest.main()
