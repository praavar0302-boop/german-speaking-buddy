import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from providers import ProviderAPIError
from scenarios import SCENARIOS


class RoleplayUiTests(unittest.TestCase):
    def test_free_conversation_is_hidden_and_opening_is_stable(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-key"}):
            app = AppTest.from_file("main.py", default_timeout=10).run()
            self.assertFalse(app.exception)
            self.assertEqual(
                [selector.label for selector in app.selectbox],
                ["AI provider", "German level", "Roleplay scenario"],
            )

            app.selectbox[2].select("Train Station").run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state.mode, "roleplay")
            self.assertEqual(app.session_state.scenario_name, "Train Station")
            opening = SCENARIOS["Train Station"]["opening_lines"]["A1"]
            self.assertEqual(
                app.session_state.conversation_history,
                [{"role": "assistant", "content": opening}],
            )

            requests = []

            def fake_stream(api_key, system_prompt, history):
                requests.append((system_prompt, list(history)))
                learner_message = history[-1]["content"]
                if learner_message == "Ich möchte nach Berlin fahren.":
                    header = (
                        '[[PROGRESS {"destination": '
                        '"Ich möchte nach Berlin fahren."}]]\n'
                    )
                else:
                    header = '[[PROGRESS {"time_platform": "Wann fährt der Zug?"}]]\n'
                return iter([header, "Der Zug fährt um acht Uhr."])

            with patch("providers.stream_gemini_response", fake_stream):
                app.chat_input[0].set_value("Ich möchte nach Berlin fahren.").run()

            self.assertFalse(app.exception)
            self.assertEqual(app.session_state.scenario_name, "Train Station")
            self.assertTrue(app.selectbox[2].disabled)
            self.assertEqual(app.session_state.scenario_progress, [True, False, False, False])
            self.assertFalse(app.session_state.scenario_complete)
            self.assertFalse(app.session_state.scenario_closing)
            self.assertEqual(len(app.checkbox), 0)
            self.assertEqual(requests[0][1][0], {"role": "assistant", "content": opening})
            self.assertEqual(
                requests[0][1][-1],
                {"role": "user", "content": "Ich möchte nach Berlin fahren."},
            )
            self.assertIn("The AI is a station employee.", requests[0][0])
            self.assertEqual(app.session_state.conversation_history[0]["content"], opening)
            self.assertEqual(app.session_state.conversation_history[-1]["role"], "assistant")

            with patch("providers.stream_gemini_response", fake_stream):
                app.chat_input[0].set_value("Wann fährt der Zug?").run()

            self.assertFalse(app.exception)
            self.assertEqual(app.session_state.scenario_name, "Train Station")
            self.assertEqual(app.session_state.scenario_progress, [True, True, False, False])
            self.assertFalse(app.session_state.scenario_complete)
            self.assertEqual(requests[1][1][-1]["content"], "Wann fährt der Zug?")
            self.assertEqual(requests[1][1][0]["content"], opening)
            self.assertEqual(requests[1][1][1]["content"], "Ich möchte nach Berlin fahren.")
            self.assertEqual(requests[1][1][2]["content"], "Der Zug fährt um acht Uhr.")

            app.run()
            self.assertEqual(app.session_state.scenario_name, "Train Station")
            self.assertEqual(app.session_state.scenario_progress, [True, True, False, False])
            self.assertEqual(len(app.checkbox), 0)
            self.assertEqual(
                app.session_state.conversation_history,
                [
                    {"role": "assistant", "content": opening},
                    {"role": "user", "content": "Ich möchte nach Berlin fahren."},
                    {"role": "assistant", "content": "Der Zug fährt um acht Uhr."},
                    {"role": "user", "content": "Wann fährt der Zug?"},
                    {"role": "assistant", "content": "Der Zug fährt um acht Uhr."},
                ],
            )

    def test_final_reply_is_saved_before_completion_and_chat_stops(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-key"}):
            app = AppTest.from_file("main.py", default_timeout=10).run()
            app.selectbox[2].select("Café").run()
            app.button[0].click().run()
            app.session_state.scenario_progress = [True, True, True, False]
            app.run()
            self.assertFalse(app.session_state.scenario_complete)
            self.assertFalse(app.chat_input[0].disabled)

            requests = []

            def fake_stream(api_key, system_prompt, history):
                requests.append(system_prompt)
                return iter([
                    '[[PROGRESS {"pay_goodbye":"Ich zahle. Auf Wiedersehen!"}]]\n',
                    "Danke! Einen schönen Tag noch!",
                ])

            with patch("providers.stream_gemini_response", fake_stream):
                with self.assertLogs("german_speaking_buddy.timing", level="INFO") as logs:
                    app.chat_input[0].set_value("Ich zahle. Auf Wiedersehen!").run()

            self.assertFalse(app.exception)
            self.assertTrue(app.session_state.scenario_complete)
            self.assertFalse(app.session_state.scenario_closing)
            self.assertEqual(app.session_state.scenario_progress, [True] * 4)
            self.assertTrue(app.chat_input[0].disabled)
            self.assertIn("Scenario complete", app.success[0].value)
            self.assertIn("brief, natural goodbye", requests[0])
            self.assertIn("no new question or task", requests[0])
            self.assertTrue(any("roleplay_timing total=" in line for line in logs.output))
            audit_line = next(
                line.split("roleplay_audit ", 1)[1]
                for line in logs.output
                if "roleplay_audit " in line
            )
            audit = json.loads(audit_line)
            self.assertEqual(audit["learner_message"], "Ich zahle. Auf Wiedersehen!")
            self.assertEqual(audit["generated_assistant_candidate"], "Danke! Einen schönen Tag noch!")
            self.assertEqual(audit["scenario_progress_evidence"]["pay_goodbye"], "Ich zahle. Auf Wiedersehen!")
            self.assertFalse(audit["fallback_used"])
            self.assertEqual(audit["decisions"][0]["action"], "DISPLAY")
            self.assertEqual(
                app.session_state.conversation_history[-2:],
                [
                    {"role": "user", "content": "Ich zahle. Auf Wiedersehen!"},
                    {"role": "assistant", "content": "Danke! Einen schönen Tag noch!"},
                ],
            )

            app.run()
            self.assertTrue(app.session_state.scenario_complete)
            self.assertTrue(app.chat_input[0].disabled)
            self.assertEqual(len(requests), 1)

            app.button[2].click().run()
            self.assertFalse(app.session_state.scenario_complete)
            self.assertEqual(app.session_state.scenario_progress, [])
            self.assertEqual(app.session_state.conversation_history, [])

    def test_bad_or_missing_final_closing_uses_reviewed_fallback(self):
        cases = {
            "rejected": "Die Implementierung erfordert eine umfassende Evaluierung.",
            "missing": "",
            "malformed": "[[broken reply]]",
            "continues roleplay": "Was möchten Sie noch trinken?",
        }
        for case, reply in cases.items():
            with self.subTest(case=case):
                with patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-key"}):
                    app = AppTest.from_file("main.py", default_timeout=10).run()
                    app.selectbox[2].select("Café").run()
                    app.button[0].click().run()
                    app.session_state.scenario_progress = [True, True, True, False]
                    app.run()

                    def fake_stream(api_key, system_prompt, history):
                        if "REVISION TASK" in system_prompt:
                            return iter([reply])
                        return iter([
                            '[[PROGRESS {"pay_goodbye":"Ich zahle. Auf Wiedersehen!"}]]\n',
                            reply,
                        ])

                    with patch("providers.stream_gemini_response", fake_stream):
                        with self.assertLogs("german_speaking_buddy.timing", level="INFO") as logs:
                            app.chat_input[0].set_value("Ich zahle. Auf Wiedersehen!").run()

                    self.assertFalse(app.exception)
                    self.assertTrue(app.session_state.scenario_complete)
                    self.assertFalse(app.session_state.scenario_closing)
                    self.assertTrue(app.chat_input[0].disabled)
                    self.assertEqual(
                        app.session_state.conversation_history[-1],
                        {"role": "assistant", "content": SCENARIOS["Café"]["fallback_closing"]},
                    )
                    audit = json.loads(
                        next(
                            line.split("roleplay_audit ", 1)[1]
                            for line in logs.output
                            if "roleplay_audit " in line
                        )
                    )
                    self.assertTrue(audit["fallback_used"])

    def test_provider_failure_shows_only_a_friendly_message(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-key", "OPENROUTER_API_KEY": ""}):
            app = AppTest.from_file("main.py", default_timeout=10).run()
            app.selectbox[2].select("Train Station").run()
            app.button[0].click().run()
            opening = list(app.session_state.conversation_history)
            attempts = []

            def fail_stream(*args):
                attempts.append(1)
                raise ProviderAPIError("gemini", 503, "UNAVAILABLE: internal detail")

            with patch("providers.stream_gemini_response", fail_stream):
                with patch("provider_retry.time.sleep"):
                    app.chat_input[0].set_value("Ich möchte nach Berlin fahren.").run()

            self.assertFalse(app.exception)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(app.session_state.conversation_history, opening)
            self.assertIn("Bitte versuche es noch einmal", app.error[0].value)
            self.assertNotIn("UNAVAILABLE", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
