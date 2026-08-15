import json
import unittest
from pathlib import Path

from engine.tet4_protocol import normalize_metadata, validate_manifest
from scripts.benchmark_batch import load_prompt_records
from scripts.generate_poem import build_prompt

ROOT = Path(__file__).resolve().parent.parent


class Tet4ProtocolTests(unittest.TestCase):
    def test_normalize_metadata_removes_duplicate_keywords(self):
        data = normalize_metadata({
            "recipient": "  ông bà ", "wish_intent": "  bình an ",
            "keywords": ["Mai vàng", "mai vàng", "sum vầy"],
        })
        self.assertEqual(data["từ khoá"], ["Mai vàng", "sum vầy"])
        self.assertEqual(data["số câu"], 4)

    def test_rejects_not_two_or_three_keywords(self):
        with self.assertRaisesRegex(ValueError, "2 hoặc 3"):
            normalize_metadata({"recipient": "mẹ", "wish_intent": "bình an", "keywords": ["xuân"]})

    def test_rejects_non_four_line_protocol(self):
        with self.assertRaisesRegex(ValueError, "num_lines=4"):
            normalize_metadata({"recipient": "mẹ", "wish_intent": "bình an", "keywords": ["xuân", "lộc"], "num_lines": 6})

    def test_manifests_are_valid_and_disjoint(self):
        sets = {}
        for split, expected_count in (("dev", 18), ("heldout", 12)):
            path = ROOT / "data" / "evaluation" / f"tet4_{split}_v1.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            records = validate_manifest(data, expected_split=split)
            self.assertEqual(len(records), expected_count)
            self.assertTrue(all(item["metadata"]["số câu"] == 4 for item in records))
            sets[split] = {item["prompt"] for item in records}
        self.assertFalse(sets["dev"] & sets["heldout"])

    def test_benchmark_loader_preserves_tet4_metadata(self):
        path = ROOT / "data" / "evaluation" / "tet4_dev_v1.json"
        records, protocol = load_prompt_records(path)
        self.assertEqual(protocol["version"], "tet4-v1")
        self.assertIn("metadata", records[0])
        prompt = build_prompt(records[0]["metadata"])
        self.assertNotIn("Người nhận lời chúc:", prompt)
        self.assertIn("Ý chúc:", prompt)
        self.assertIn("Số câu: 4", prompt)

    def test_recipient_is_optional_in_product_schema(self):
        data = normalize_metadata({
            "wish_intent": "chúc ông bà bình an, gia đình sum vầy",
            "keywords": ["mai vàng", "đoàn viên"],
        })
        self.assertEqual(data["ý chúc"], "chúc ông bà bình an, gia đình sum vầy")
        self.assertNotIn("người nhận", data)


if __name__ == "__main__":
    unittest.main()
