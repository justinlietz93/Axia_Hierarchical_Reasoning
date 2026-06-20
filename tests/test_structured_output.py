from __future__ import annotations

import unittest

from axia.formation import parse_and_validate_json_object


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "count"],
    "properties": {
        "status": {"type": "string", "enum": ["ok"]},
        "count": {"type": "integer", "minimum": 1},
    },
}


class StructuredOutputTests(unittest.TestCase):
    def test_accepts_valid_typed_json(self) -> None:
        result = parse_and_validate_json_object('{"status":"ok","count":1}', SCHEMA)

        self.assertTrue(result.accepted)
        self.assertEqual(result.payload, {"status": "ok", "count": 1})
        self.assertEqual(result.validation_errors, ())

    def test_preserves_parse_missing_field_and_wrong_type_errors(self) -> None:
        cases = (
            ("{", "json_parse", "$"),
            ('{"status":"ok"}', "required", "$.count"),
            ('{"status":"ok","count":"one"}', "type", "$.count"),
        )
        for response_text, rule, path in cases:
            with self.subTest(response_text=response_text):
                result = parse_and_validate_json_object(response_text, SCHEMA)

                self.assertFalse(result.accepted)
                self.assertIsNone(result.payload)
                self.assertEqual(result.validation_errors[0].rule, rule)
                self.assertEqual(result.validation_errors[0].path, path)
