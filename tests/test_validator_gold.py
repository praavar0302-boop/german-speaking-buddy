"""Schema and execution checks for the hand-reviewed vocabulary gold corpus.

Expectation mismatches are reported by evaluate_gold_corpus.py. They do not
make this structural test fail because the corpus intentionally characterizes
known validator limitations before runtime integration.
"""

import json
import unittest
from collections import Counter
from pathlib import Path

from validator import (
    ABOVE_LEVEL,
    ALLOWED,
    EXEMPT,
    FAIL,
    PASS,
    UNKNOWN,
    UNVERIFIED,
    validate_vocabulary,
)


CORPUS_PATH = Path(__file__).with_name("gold_vocabulary_cases.jsonl")
REQUIRED_CATEGORIES = {
    "normal_a1",
    "normal_a2",
    "a2_under_a1",
    "inflection",
    "function_words",
    "contractions",
    "separable_verbs",
    "proper_nouns",
    "numbers_dates_times",
    "compounds",
    "outside_lexicon",
    "ambiguous",
}


def load_gold_cases():
    return [
        json.loads(line)
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class VocabularyGoldCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_gold_cases()

    def test_corpus_shape_and_coverage(self):
        self.assertGreaterEqual(len(self.cases), 80)
        self.assertLessEqual(len(self.cases), 100)
        self.assertEqual(len({case["id"] for case in self.cases}), len(self.cases))
        self.assertEqual({case["category"] for case in self.cases}, REQUIRED_CATEGORIES)

        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    set(case) - {"session_terms"},
                    {"id", "category", "sentence", "level", "expected", "reason"},
                )
                self.assertIn(case["level"], {"A1", "A2"})
                self.assertIn(case["expected"], {PASS, FAIL, UNKNOWN})
                self.assertTrue(case["sentence"].strip())
                self.assertTrue(case["reason"].strip())

    def test_every_case_executes_with_auditable_tokens(self):
        actual_counts = Counter()
        for case in self.cases:
            with self.subTest(case=case["id"]):
                result = validate_vocabulary(
                    case["sentence"],
                    case["level"],
                    session_terms=case.get("session_terms"),
                )
                actual_counts[result["status"]] += 1
                self.assertIn(result["status"], {PASS, FAIL, UNKNOWN})
                self.assertTrue(result["tokens"])
                for token in result["tokens"]:
                    self.assertIn(
                        token["classification"],
                        {ALLOWED, ABOVE_LEVEL, UNVERIFIED, EXEMPT},
                    )
                    self.assertIn(
                        token["reason"],
                        {
                            "exact",
                            "lemma",
                            "contraction",
                            "compound",
                            "function word",
                            "number",
                            "session_term",
                            "unknown",
                        },
                    )

                diagnostics = result["diagnostics"]
                self.assertEqual(
                    diagnostics["allowed_token_count"]
                    + diagnostics["unverified_token_count"]
                    + diagnostics["above_level_token_count"]
                    + diagnostics["exempt_token_count"],
                    len(result["tokens"]),
                )
                coverage = diagnostics["lexical_coverage"]
                self.assertTrue(coverage is None or 0 <= coverage <= 1)

        self.assertEqual(sum(actual_counts.values()), len(self.cases))


if __name__ == "__main__":
    unittest.main()
