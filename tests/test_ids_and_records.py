import unittest

from axia.shared.ids import ArtifactId, RunId, stable_json_hash
from axia.source import ArtifactLineage, RequestRecord


class IdAndRecordTests(unittest.TestCase):
    def test_stable_json_hash_ignores_key_order(self) -> None:
        self.assertEqual(
            stable_json_hash({"b": 2, "a": 1}),
            stable_json_hash({"a": 1, "b": 2}),
        )

    def test_request_record_hashes_raw_text(self) -> None:
        first = RequestRecord.from_text("compare databases")
        second = RequestRecord.from_text("compare databases")
        self.assertEqual(first.content_hash, second.content_hash)

    def test_artifact_lineage_requires_source_hash(self) -> None:
        with self.assertRaises(ValueError):
            ArtifactLineage.from_sources(ArtifactId.new(), RunId.new(), ())


if __name__ == "__main__":
    unittest.main()

