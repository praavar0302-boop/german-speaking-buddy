import unittest
from unittest.mock import patch

from decision_layer import DISPLAY, DISPLAY_AND_RECORD, decide_response

from scenarios import (
    SCENARIOS,
    SCENARIO_OPTIONS,
    choose_random_scenario,
    format_scenario_prompt,
    is_closing_reply,
    opening_line,
    scenario_is_complete,
)


class ScenarioTests(unittest.TestCase):
    def test_required_scenarios_have_complete_data(self):
        expected = {
            "Café",
            "Restaurant",
            "Supermarket",
            "Asking for Directions",
            "Train Station",
            "Pharmacy",
            "Hotel",
            "Airport",
        }
        self.assertEqual(set(SCENARIOS), expected)
        self.assertEqual(SCENARIO_OPTIONS[-1], "Random")

        for name, scenario in SCENARIOS.items():
            with self.subTest(scenario=name):
                self.assertTrue(scenario["title"])
                self.assertTrue(scenario["learner_role"])
                self.assertTrue(scenario["ai_role"])
                self.assertGreaterEqual(len(scenario["objectives"]), 3)
                self.assertLessEqual(len(scenario["objectives"]), 5)
                self.assertEqual(
                    len({objective["id"] for objective in scenario["objectives"]}),
                    len(scenario["objectives"]),
                )
                self.assertTrue(all(objective["text"] for objective in scenario["objectives"]))
                self.assertTrue(scenario["completion_condition"])
                self.assertEqual(set(scenario["opening_lines"]), {"A1", "A2"})
                self.assertTrue(scenario["fallback_closing"])

    def test_reviewed_opening_lines_are_deterministic_and_accepted(self):
        for name, scenario in SCENARIOS.items():
            for level in ("A1", "A2"):
                with self.subTest(scenario=name, level=level):
                    line = opening_line(scenario, level)
                    self.assertEqual(line, opening_line(scenario, level))
                    self.assertEqual(decide_response(line, level)["action"], DISPLAY)

    def test_reviewed_fallback_closings_pass_both_levels(self):
        for name, scenario in SCENARIOS.items():
            for level in ("A1", "A2"):
                with self.subTest(scenario=name, level=level):
                    line = scenario["fallback_closing"]
                    self.assertTrue(is_closing_reply(line))
                    self.assertIn(
                        decide_response(line, level)["action"],
                        {DISPLAY, DISPLAY_AND_RECORD},
                    )

    def test_closing_does_not_allow_a_following_task(self):
        self.assertFalse(is_closing_reply("Auf Wiedersehen! Kaufen Sie noch Brot."))
        self.assertFalse(is_closing_reply("Danke! Möchten Sie noch etwas?"))

    def test_random_selects_a_real_scenario(self):
        with patch("scenarios.random.choice", return_value="Hotel"):
            self.assertEqual(choose_random_scenario(), "Hotel")

    def test_completion_requires_every_objective(self):
        scenario = SCENARIOS["Café"]
        self.assertFalse(scenario_is_complete(scenario, [True, True, True, False]))
        self.assertTrue(scenario_is_complete(scenario, [True, True, True, True]))

    def test_prompt_contains_roles_objectives_and_progress(self):
        scenario = SCENARIOS["Café"]
        prompt = format_scenario_prompt(scenario, [True, False, False, False])
        self.assertIn(scenario["learner_role"], prompt)
        self.assertIn(scenario["ai_role"], prompt)
        self.assertIn("[done]", prompt)
        self.assertIn("[remaining]", prompt)
        self.assertIn(scenario["completion_condition"], prompt)
        self.assertIn("remaining objectives", prompt)
        self.assertIn("not as a generic assistant", prompt)
        self.assertIn("most recent message", prompt)
        self.assertIn("one small step at a time", prompt)

    def test_every_prompt_contains_the_correct_roles_and_objectives(self):
        for name, scenario in SCENARIOS.items():
            with self.subTest(scenario=name):
                prompt = format_scenario_prompt(
                    scenario, [False] * len(scenario["objectives"])
                )
                self.assertIn(scenario["learner_role"], prompt)
                self.assertIn(scenario["ai_role"], prompt)
                for objective in scenario["objectives"]:
                    self.assertIn(objective["id"], prompt)
                    self.assertIn(objective["text"], prompt)

    def test_prompt_requests_a_natural_closing_when_final_objective_is_met(self):
        scenario = SCENARIOS["Café"]
        prompt = format_scenario_prompt(scenario, [True, True, True, False])
        self.assertIn("[remaining] pay_goodbye", prompt)
        self.assertIn("brief, natural goodbye", prompt)
        self.assertIn("Do not introduce another task", prompt)


if __name__ == "__main__":
    unittest.main()
