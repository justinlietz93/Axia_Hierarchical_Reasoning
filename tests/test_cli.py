import contextlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from axia.boundary.presentation.cli import main
from axia.boundary.presentation.standalone_runtime import StandaloneRuntime
from axia.projection import ModelProfileIdentity
from axia.shared.ids import stable_text_hash
from tests.test_run_controller import ScriptedProvider


class CliTests(unittest.TestCase):
    def test_version_command(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["--version"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(output.getvalue().strip())

    def test_ask_command_executes_and_persists_a_local_run(self) -> None:
        runtime = StandaloneRuntime(
            provider=ScriptedProvider(),
            profile=None,  # type: ignore[arg-type]
            profile_identity=ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
        )
        with TemporaryDirectory() as temporary_directory:
            output = StringIO()
            with patch("axia.boundary.presentation.cli.compose_standalone_runtime", return_value=runtime):
                with contextlib.redirect_stdout(output):
                    exit_code = main(
                        [
                            "ask",
                            "compare",
                            "databases",
                            "--run-store",
                            str(Path(temporary_directory) / "runs.sqlite3"),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["mode"], "quick")
        self.assertTrue(payload["run_id"].startswith("run_"))

    def test_benchmark_command_is_registered(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["benchmark", "run", "--suite", "baseline"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["suite"], "baseline")

    def test_profiles_list_reports_the_standalone_profile(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["profiles", "list"])

        self.assertEqual(exit_code, 0)
        profiles = json.loads(output.getvalue())
        self.assertEqual(profiles[0]["name"], "tiny-default")

    def test_provider_stdout_is_redirected_away_from_machine_readable_cli_output(self) -> None:
        class NoisyProvider(ScriptedProvider):
            def generate(self, request):  # type: ignore[no-untyped-def]
                print("provider diagnostic")
                return super().generate(request)

        runtime = StandaloneRuntime(
            provider=NoisyProvider(),
            profile=None,  # type: ignore[arg-type]
            profile_identity=ModelProfileIdentity(
                name="tiny-test",
                profile_hash=stable_text_hash("tiny-test"),
                provider_metadata={"provider": "scripted", "model": "scripted-tiny"},
            ),
        )
        with TemporaryDirectory() as temporary_directory:
            output = StringIO()
            with patch("axia.boundary.presentation.cli.compose_standalone_runtime", return_value=runtime):
                with contextlib.redirect_stdout(output):
                    exit_code = main(
                        [
                            "ask",
                            "compare",
                            "databases",
                            "--run-store",
                            str(Path(temporary_directory) / "runs.sqlite3"),
                        ]
                    )

        self.assertEqual(exit_code, 0)
        self.assertNotIn("provider diagnostic", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"], "complete")


if __name__ == "__main__":
    unittest.main()
