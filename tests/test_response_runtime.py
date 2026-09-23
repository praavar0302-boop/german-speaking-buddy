import unittest
import time

from decision_layer import DISPLAY, DISPLAY_AND_RECORD, FALLBACK, REGENERATE
from language_validator import PASS, VIOLATION, WARNING
from response_runtime import (
    FALLBACK_SENTENCE,
    TYPING_MESSAGE,
    commit_accepted_exchange,
    first_validated_chunks,
    timed_model_chunks,
    validated_response_stream,
)


def decision(
    text,
    action,
    *,
    attempt=0,
    unverified=None,
    language_status=PASS,
    warnings=None,
    violations=None,
    reasons=None,
):
    unverified = unverified or []
    warnings = warnings or []
    violations = violations or []
    return {
        "action": action,
        "level": "A1",
        "attempt": attempt,
        "selected_attempt": attempt,
        "text": text,
        "reason_codes": reasons or [],
        "vocabulary": {
            "unverified_content_words": unverified,
        },
        "language": {
            "status": language_status,
            "warning_count": len(warnings),
            "violation_count": len(violations),
            "warnings": warnings,
            "violations": violations,
        },
        "record_for_feedback": {
            "uncertain_vocabulary": unverified,
            "language_warnings": warnings,
        },
    }


def run_stream(initial, decide, rewrite=lambda *_: ()):
    feedback = {"uncertain_vocabulary": [], "language_warnings": []}
    output = "".join(
        validated_response_stream(
            initial,
            "A1",
            rewrite,
            feedback,
            decision_fn=decide,
        )
    )
    return output, feedback


class ResponseRuntimeTests(unittest.TestCase):
    def test_first_pass_accepted_sentence(self):
        calls = []

        def decide(text, level, **kwargs):
            calls.append(text)
            return decision(text, DISPLAY)

        output, _ = run_stream(["Ich lerne", " Deutsch. Noch etwas."], decide)
        self.assertEqual(output, "Ich lerne Deutsch. Noch etwas.")
        self.assertEqual(calls, ["Ich lerne Deutsch.", "Noch etwas."])

    def test_vocabulary_only_correction(self):
        rewrite_calls = []

        def decide(text, level, attempt=0, **kwargs):
            if text == "Ich kaufe ein Quantenobjekt.":
                return decision(
                    text,
                    REGENERATE,
                    attempt=attempt,
                    unverified=["Quantenobjekt"],
                    reasons=["ONE_UNVERIFIED_WITHOUT_ALLOWED_CONTENT"],
                )
            return decision(text, DISPLAY, attempt=attempt)

        def rewrite(sentence, instruction, attempt):
            rewrite_calls.append((sentence, instruction, attempt))
            return ["Ich kaufe ein Gerät."]

        output, _ = run_stream(["Ich kaufe ein Quantenobjekt."], decide, rewrite)
        self.assertEqual(output, "Ich kaufe ein Gerät.")
        self.assertIn("replace only", rewrite_calls[0][1])
        self.assertIn("Quantenobjekt", rewrite_calls[0][1])

    def test_structural_rewrite(self):
        instructions = []

        def decide(text, level, attempt=0, **kwargs):
            if text.startswith("Obwohl"):
                violation = {"metric": "subordination_depth", "status": VIOLATION}
                return decision(
                    text,
                    REGENERATE,
                    attempt=attempt,
                    language_status=VIOLATION,
                    violations=[violation],
                    reasons=["LANGUAGE_VIOLATION"],
                )
            return decision(text, DISPLAY, attempt=attempt)

        def rewrite(sentence, instruction, attempt):
            instructions.append(instruction)
            return ["Ich bin müde. Ich bleibe zu Hause."]

        output, _ = run_stream(
            ["Obwohl ich müde bin, bleibe ich zu Hause."], decide, rewrite
        )
        self.assertEqual(output, "Ich bin müde. Ich bleibe zu Hause.")
        self.assertIn("subordination_depth", instructions[0])
        self.assertNotIn("replace only", instructions[0])

    def test_retry_limit_uses_fallback(self):
        rewrite_attempts = []

        def decide(text, level, attempt=0, **kwargs):
            if text == FALLBACK_SENTENCE:
                return decision(text, DISPLAY)
            if attempt == 2:
                return decision(None, FALLBACK, attempt=attempt)
            return decision(
                text,
                REGENERATE,
                attempt=attempt,
                language_status=VIOLATION,
                violations=[{"metric": "sentence", "status": VIOLATION}],
                reasons=["LANGUAGE_VIOLATION"],
            )

        def rewrite(sentence, instruction, attempt):
            rewrite_attempts.append(attempt)
            return [f"Versuch {attempt}."]

        output, _ = run_stream(["Zu kompliziert."], decide, rewrite)
        self.assertEqual(output, FALLBACK_SENTENCE)
        self.assertEqual(rewrite_attempts, [1, 2])

    def test_only_accepted_text_enters_history(self):
        history = [{"role": "assistant", "content": "Hallo!"}]
        self.assertFalse(commit_accepted_exchange(history, "Test", ""))
        self.assertEqual(len(history), 1)

        self.assertTrue(commit_accepted_exchange(history, "Wie geht es?", "Gut."))
        self.assertEqual(
            history[-2:],
            [
                {"role": "user", "content": "Wie geht es?"},
                {"role": "assistant", "content": "Gut."},
            ],
        )

    def test_feedback_items_are_stored(self):
        warning = {"feature": "passive", "status": WARNING}

        def decide(text, level, **kwargs):
            return decision(
                text,
                DISPLAY_AND_RECORD,
                unverified=["Adapter"],
                language_status=WARNING,
                warnings=[warning],
            )

        _, feedback = run_stream(["Ich brauche einen Adapter."], decide)
        self.assertEqual(feedback["uncertain_vocabulary"], ["Adapter"])
        self.assertEqual(feedback["language_warnings"], [warning])

    def test_typing_message_does_not_expose_validator_details(self):
        self.assertIn("tippt", TYPING_MESSAGE)
        self.assertNotIn("validator", TYPING_MESSAGE.casefold())
        self.assertNotIn("violation", TYPING_MESSAGE.casefold())
        self.assertNotIn("unverified", TYPING_MESSAGE.casefold())

    def test_timing_counts_validation_rewrites_and_first_ready(self):
        diagnostics = {
            "started_at": time.perf_counter(),
            "model_seconds": 0.0,
            "validation_seconds": 0.0,
            "rewrites": 0,
            "first_validated_seconds": None,
        }

        def decide(text, level, **kwargs):
            if text == "Schweres Wort.":
                return decision(
                    text,
                    REGENERATE,
                    unverified=["Schweres"],
                    reasons=["ONE_UNVERIFIED_WITHOUT_ALLOWED_CONTENT"],
                )
            return decision(text, DISPLAY)

        def rewrite(*_):
            return timed_model_chunks(["Einfaches Wort."], diagnostics)

        feedback = {"uncertain_vocabulary": [], "language_warnings": []}
        output = "".join(
            first_validated_chunks(
                validated_response_stream(
                    timed_model_chunks(["Schweres Wort."], diagnostics),
                    "A1",
                    rewrite,
                    feedback,
                    decision_fn=decide,
                    diagnostics=diagnostics,
                ),
                diagnostics,
            )
        )
        self.assertEqual(output, "Einfaches Wort.")
        self.assertEqual(diagnostics["rewrites"], 1)
        self.assertEqual(diagnostics["generated_candidates"], ["Schweres Wort."])
        self.assertEqual(diagnostics["rewritten_candidates"], ["Einfaches Wort."])
        self.assertEqual(
            [item["action"] for item in diagnostics["decisions"]],
            [REGENERATE, DISPLAY],
        )
        self.assertEqual(
            diagnostics["decisions"][0]["unverified_vocabulary"],
            ["Schweres"],
        )
        self.assertGreaterEqual(diagnostics["model_seconds"], 0)
        self.assertGreater(diagnostics["validation_seconds"], 0)
        self.assertIsNotNone(diagnostics["first_validated_seconds"])


if __name__ == "__main__":
    unittest.main()
