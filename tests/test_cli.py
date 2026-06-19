import contextlib
from io import StringIO
import json
import unittest

from axia.boundary.presentation.cli import main


class CliTests(unittest.TestCase):
    def test_version_command(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["--version"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(output.getvalue().strip())

    def test_ask_command_emits_request_hash(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["ask", "compare", "databases"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["command"], "ask")
        self.assertEqual(payload["status"], "not_implemented")
        self.assertIn("request_hash", payload)

    def test_benchmark_command_is_registered(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["benchmark", "run", "--suite", "baseline"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["suite"], "baseline")


if __name__ == "__main__":
    unittest.main()

