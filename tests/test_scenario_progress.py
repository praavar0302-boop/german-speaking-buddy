import unittest

from scenario_progress import (
    progress_instruction,
    split_progress_header,
    update_progress,
)
from scenarios import SCENARIOS


class ScenarioProgressTests(unittest.TestCase):
    def setUp(self):
        self.scenario = SCENARIOS["Café"]
        self.empty = [False] * len(self.scenario["objectives"])

    def test_one_objective_completed(self):
        evidence = {"ask_price": "Was kostet der Kaffee?"}
        updated = update_progress(
            self.scenario, self.empty, evidence, "Was kostet der Kaffee?"
        )
        self.assertEqual(updated, [False, False, True, False])

    def test_multiple_objectives_in_one_message(self):
        message = "Guten Tag! Ich möchte einen Kaffee."
        evidence = {"greet": "Guten Tag!", "order_drink": "Ich möchte einen Kaffee."}
        updated = update_progress(self.scenario, self.empty, evidence, message)
        self.assertEqual(updated, [True, True, False, False])

    def test_paraphrased_price_question(self):
        message = "Wie viel kostet das?"
        evidence = {"ask_price": "Wie viel kostet das?"}
        updated = update_progress(self.scenario, self.empty, evidence, message)
        self.assertTrue(updated[2])

    def test_ai_text_cannot_complete_learner_objective(self):
        evidence = {"ask_price": "Der Kaffee kostet drei Euro."}
        updated = update_progress(self.scenario, self.empty, evidence, "Ich möchte Tee.")
        self.assertEqual(updated, self.empty)

    def test_progress_persists_and_never_reverts(self):
        first = update_progress(
            self.scenario,
            self.empty,
            {"greet": "Hallo!"},
            "Hallo!",
        )
        second = update_progress(
            self.scenario,
            first,
            {"ask_price": "Wie viel kostet das?"},
            "Wie viel kostet das?",
        )
        third = update_progress(self.scenario, second, {}, "Danke.")
        self.assertEqual(third, [True, False, True, False])
        self.assertEqual(self.empty, [False] * 4)

    def test_unknown_ids_and_empty_evidence_are_ignored(self):
        updated = update_progress(
            self.scenario,
            self.empty,
            {"not_an_objective": "Hallo!", "greet": ""},
            "Hallo!",
        )
        self.assertEqual(updated, self.empty)

    def test_header_is_removed_from_chunked_stream(self):
        chunks = [
            '[[PRO',
            'GRESS {"ask_price":"Wie viel kostet das?"}]]\n',
            "Das kostet ",
            "drei Euro.",
        ]
        evidence, reply = split_progress_header(chunks)
        self.assertEqual(evidence, {"ask_price": "Wie viel kostet das?"})
        self.assertEqual("".join(reply), "Das kostet drei Euro.")

    def test_missing_header_keeps_reply(self):
        evidence, reply = split_progress_header(["Guten Tag!", " Was möchten Sie?"])
        self.assertEqual(evidence, {})
        self.assertEqual("".join(reply), "Guten Tag! Was möchten Sie?")

    def test_progress_instruction_uses_scenario_ids_and_learner_evidence(self):
        instruction = progress_instruction(self.scenario)
        for objective in self.scenario["objectives"]:
            self.assertIn(objective["id"], instruction)
        self.assertIn("latest learner message", instruction)
        self.assertIn("never report an action merely because you mentioned it", instruction)


if __name__ == "__main__":
    unittest.main()
