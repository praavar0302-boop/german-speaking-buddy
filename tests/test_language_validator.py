import json
import unittest
from pathlib import Path

from language_validator import PASS, VIOLATION, WARNING, validate_structure


CORPUS_PATH = Path(__file__).with_name("structural_validation_cases.jsonl")


def load_structural_cases():
    return [
        json.loads(line)
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class LanguageValidatorTests(unittest.TestCase):
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

    def test_subordinate_connectors_share_clause_analysis(self):
        for connector in ("weil", "dass", "wenn", "ob"):
            sentence = {
                "weil": "Ich bleibe hier, weil ich müde bin.",
                "dass": "Ich weiß, dass du heute kommst.",
                "wenn": "Wenn es regnet, bleibe ich hier.",
                "ob": "Ich weiß nicht, ob er kommt.",
            }[connector]
            with self.subTest(connector=connector):
                a1 = validate_structure(sentence, "A1")
                a2 = validate_structure(sentence, "A2")
                self.assertEqual(a1["status"], VIOLATION)
                self.assertEqual(a2["status"], PASS)
                observed = [
                    feature["observed"]["connector"]
                    for feature in a2["features"]
                    if feature["feature"] == "subordinate_connector"
                ]
                self.assertEqual(observed, [connector])

        uncertain = validate_structure(
            "Ich bleibe hier, obwohl ich müde bin.", "A2"
        )
        self.assertEqual(uncertain["status"], WARNING)

    def test_relative_clause_behavior(self):
        text = "Das ist der Mann, der hier wohnt."
        self.assertEqual(validate_structure(text, "A1")["status"], VIOLATION)
        a2 = validate_structure(text, "A2")
        self.assertEqual(a2["status"], PASS)
        relative = next(
            feature for feature in a2["features"] if feature["feature"] == "relative_clause"
        )
        self.assertEqual(relative["observed"]["depth"], 1)

    def test_tense_patterns(self):
        self.assertEqual(validate_structure("Ich habe gegessen.", "A1")["status"], PASS)
        self.assertEqual(
            validate_structure("Ich hatte gegessen.", "A1")["status"], VIOLATION
        )
        self.assertEqual(
            validate_structure("Ich hatte gegessen.", "A2")["status"], WARNING
        )

    def test_allowed_modal_is_audited_without_violation(self):
        for text, expected_lemma in (
            ("Ich kann heute kommen.", "können"),
            ("Ich muss heute arbeiten.", "müssen"),
        ):
            with self.subTest(text=text):
                result = validate_structure(text, "A1")
                self.assertEqual(result["status"], PASS)
                modal = next(
                    feature
                    for feature in result["features"]
                    if feature["feature"] == "modal_verbs"
                )
                self.assertEqual(modal["status"], PASS)
                self.assertEqual(modal["observed"]["verbs"][0]["lemma"], expected_lemma)

    def test_zu_infinitive_behavior(self):
        text = "Ich versuche, Deutsch zu lernen."
        self.assertEqual(validate_structure(text, "A1")["status"], WARNING)
        self.assertEqual(validate_structure(text, "A2")["status"], PASS)

    def test_passive_behavior(self):
        text = "Das Haus wird gebaut."
        self.assertEqual(validate_structure(text, "A1")["status"], VIOLATION)
        self.assertEqual(validate_structure(text, "A2")["status"], PASS)

        advanced = validate_structure("Das Haus ist gebaut worden.", "A2")
        self.assertEqual(advanced["status"], WARNING)


if __name__ == "__main__":
    unittest.main()
