import json
import unittest
from pathlib import Path

from structural_validator import PASS, VIOLATION, validate_structure


CORPUS_PATH = Path(__file__).with_name("structural_validation_cases.jsonl")


def load_structural_cases():
    return [
        json.loads(line)
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class StructuralValidatorTests(unittest.TestCase):
    def test_corpus(self):
        cases = load_structural_cases()
        self.assertEqual(len(cases), 17)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                result = validate_structure(case["text"], case["level"])
                self.assertEqual(result["status"], case["expected"], result)
                self.assertEqual(len(result["metrics"]), 5)
                for metric in result["metrics"]:
                    self.assertIn(metric["status"], {PASS, VIOLATION})
                    self.assertIn("observed", metric)
                    self.assertIn("configured_limit", metric)

    def test_limits_come_from_level_policy(self):
        a1 = validate_structure("Hallo.", "A1")
        a2 = validate_structure("Hallo.", "A2")
        a1_metrics = {metric["metric"]: metric for metric in a1["metrics"]}
        a2_metrics = {metric["metric"]: metric for metric in a2["metrics"]}
        self.assertEqual(a1_metrics["sentence_count"]["configured_limit"], 4)
        self.assertEqual(a2_metrics["sentence_count"]["configured_limit"], 6)
        self.assertEqual(a1_metrics["subordination_depth"]["configured_limit"], 0)
        self.assertEqual(a2_metrics["subordination_depth"]["configured_limit"], 1)

    def test_invalid_level(self):
        with self.assertRaises(ValueError):
            validate_structure("Hallo.", "B1")


if __name__ == "__main__":
    unittest.main()
