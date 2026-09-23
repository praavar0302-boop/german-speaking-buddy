import unittest

from decision_layer import (
    DISPLAY,
    DISPLAY_AND_RECORD,
    FALLBACK,
    REGENERATE,
    decide_from_results,
    decide_response,
)
from language_validator import PASS, VIOLATION, WARNING
from validator import ALLOWED, EXEMPT, UNVERIFIED


def vocabulary_result(allowed=0, unverified=0, exempt=0, coverage=1.0):
    tokens = []
    for index in range(allowed):
        tokens.append(
            {
                "token": f"allowed{index}",
                "classification": ALLOWED,
                "is_content": True,
            }
        )
    for index in range(unverified):
        tokens.append(
            {
                "token": f"unknown{index}",
                "classification": UNVERIFIED,
                "is_content": True,
            }
        )
    for index in range(exempt):
        tokens.append(
            {
                "token": f"exempt{index}",
                "classification": EXEMPT,
                "is_content": True,
            }
        )
    return {
        "tokens": tokens,
        "diagnostics": {
            "allowed_token_count": allowed,
            "unverified_token_count": unverified,
            "above_level_token_count": 0,
            "exempt_token_count": exempt,
            "lexical_coverage": coverage,
            "unverified_content_words": [
                f"unknown{index}" for index in range(unverified)
            ],
        },
    }


def language_result(status=PASS, warnings=0, violations=0):
    features = [
        {"feature": f"warning{index}", "status": WARNING}
        for index in range(warnings)
    ]
    features.extend(
        {"feature": f"violation{index}", "status": VIOLATION}
        for index in range(violations)
    )
    return {"status": status, "metrics": [], "features": features}


def decide(vocabulary, language, **kwargs):
    return decide_from_results(
        "Testantwort.", "A1", vocabulary, language, **kwargs
    )


class DecisionLayerTests(unittest.TestCase):
    def test_language_violation_always_regenerates(self):
        result = decide(
            vocabulary_result(allowed=10),
            language_result(VIOLATION, violations=1),
        )
        self.assertEqual(result["action"], REGENERATE)
        self.assertIn("LANGUAGE_VIOLATION", result["reason_codes"])

    def test_clean_response_displays(self):
        result = decide(vocabulary_result(allowed=3), language_result())
        self.assertEqual(result["action"], DISPLAY)

    def test_one_unverified_with_allowed_content_displays_and_records(self):
        result = decide(vocabulary_result(allowed=1, unverified=1), language_result())
        self.assertEqual(result["action"], DISPLAY_AND_RECORD)
        self.assertEqual(
            result["record_for_feedback"]["uncertain_vocabulary"], ["unknown0"]
        )

    def test_one_unverified_without_allowed_content_regenerates(self):
        result = decide(vocabulary_result(unverified=1, coverage=0), language_result())
        self.assertEqual(result["action"], REGENERATE)

    def test_two_unverified_require_pass_and_four_allowed(self):
        accepted = decide(
            vocabulary_result(allowed=4, unverified=2), language_result(PASS)
        )
        self.assertEqual(accepted["action"], DISPLAY_AND_RECORD)

        too_little_evidence = decide(
            vocabulary_result(allowed=3, unverified=2), language_result(PASS)
        )
        self.assertEqual(too_little_evidence["action"], REGENERATE)

        warning = decide(
            vocabulary_result(allowed=4, unverified=2),
            language_result(WARNING, warnings=1),
        )
        self.assertEqual(warning["action"], REGENERATE)

    def test_three_unverified_regenerate(self):
        result = decide(
            vocabulary_result(allowed=10, unverified=3), language_result()
        )
        self.assertEqual(result["action"], REGENERATE)

    def test_warning_behavior(self):
        one_warning = decide(
            vocabulary_result(allowed=3), language_result(WARNING, warnings=1)
        )
        self.assertEqual(one_warning["action"], DISPLAY)
        self.assertEqual(
            len(one_warning["record_for_feedback"]["language_warnings"]), 1
        )

        warning_with_unknown = decide(
            vocabulary_result(allowed=2, unverified=1),
            language_result(WARNING, warnings=1),
        )
        self.assertEqual(warning_with_unknown["action"], DISPLAY_AND_RECORD)

        multiple = decide(
            vocabulary_result(allowed=3), language_result(WARNING, warnings=2)
        )
        self.assertEqual(multiple["action"], REGENERATE)

    def test_lexical_coverage_is_diagnostic_only(self):
        result = decide(
            vocabulary_result(allowed=1, unverified=1, coverage=0.01),
            language_result(PASS),
        )
        self.assertEqual(result["action"], DISPLAY_AND_RECORD)
        self.assertEqual(result["vocabulary"]["lexical_coverage"], 0.01)

    def test_exempt_only_response_displays(self):
        result = decide(vocabulary_result(exempt=2, coverage=None), language_result())
        self.assertEqual(result["action"], DISPLAY)
        self.assertIn("EXEMPT_ONLY_RESPONSE", result["reason_codes"])

    def test_retry_limit_and_safest_candidate_selection(self):
        first = decide(
            vocabulary_result(allowed=2, unverified=3, coverage=0.4),
            language_result(PASS),
            attempt=0,
        )
        second = decide(
            vocabulary_result(allowed=3, unverified=3, coverage=0.5),
            language_result(WARNING, warnings=1),
            attempt=1,
            previous_candidates=[first],
        )
        final = decide(
            vocabulary_result(allowed=5, unverified=3, coverage=0.6),
            language_result(PASS),
            attempt=2,
            previous_candidates=[first, second],
        )

        self.assertEqual(first["action"], REGENERATE)
        self.assertEqual(second["action"], REGENERATE)
        self.assertEqual(final["action"], DISPLAY_AND_RECORD)
        self.assertEqual(final["selected_attempt"], 2)
        self.assertIn("SAFEST_CANDIDATE_SELECTED", final["reason_codes"])

    def test_exhausted_violations_use_fallback(self):
        candidates = []
        for attempt in range(3):
            result = decide(
                vocabulary_result(allowed=5),
                language_result(VIOLATION, violations=1),
                attempt=attempt,
                previous_candidates=candidates,
            )
            if attempt < 2:
                self.assertEqual(result["action"], REGENERATE)
                candidates.append(result)

        self.assertEqual(result["action"], FALLBACK)
        self.assertIsNone(result["text"])
        self.assertIn("NO_SAFE_CANDIDATE", result["reason_codes"])

    def test_invalid_attempt_is_rejected(self):
        with self.assertRaises(ValueError):
            decide(
                vocabulary_result(allowed=1), language_result(), attempt=3
            )

    def test_real_validators_are_combined(self):
        result = decide_response("Ich lerne Deutsch.", "A1")
        self.assertIn(result["action"], {DISPLAY, DISPLAY_AND_RECORD})
        self.assertEqual(result["level"], "A1")


if __name__ == "__main__":
    unittest.main()
