"""Structural checks for the independent 150-case evaluation corpus."""

import json
import unittest
from pathlib import Path


CORPUS_PATH = Path(__file__).with_name("generalization_vocabulary_cases.jsonl")


def load_generalization_cases():
    return [
        json.loads(line)
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeneralizationCorpusTests(unittest.TestCase):
    def test_corpus_is_complete_and_well_formed(self):
        cases = load_generalization_cases()
        self.assertEqual(len(cases), 150)
        self.assertEqual(len({case["id"] for case in cases}), 150)
        self.assertEqual(len({case["category"] for case in cases}), 15)

        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    set(case) - {"session_terms"},
                    {"id", "category", "sentence", "level", "expected", "reason"},
                )
                self.assertIn(case["level"], {"A1", "A2"})
                self.assertIn(case["expected"], {"PASS", "FAIL", "UNKNOWN"})
                self.assertTrue(case["sentence"].strip())
                self.assertTrue(case["reason"].strip())


if __name__ == "__main__":
    unittest.main()
