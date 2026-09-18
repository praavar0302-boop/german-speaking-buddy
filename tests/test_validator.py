import unittest

from validator import ALLOWED, EXEMPT, PASS, UNKNOWN, UNVERIFIED, validate_vocabulary


class VocabularyValidatorTests(unittest.TestCase):
    def assert_status(self, text, level, expected, **kwargs):
        result = validate_vocabulary(text, level, **kwargs)
        self.assertEqual(result["status"], expected, result)
        return result

    def test_required_a1_sentences(self):
        sentences = (
            "Ich gehe heute zur Arbeit.",
            "Ich möchte einen Kaffee.",
            "Meine Freunde wohnen in Berlin.",
        )
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                session_terms = {"Berlin"} if "Berlin" in sentence else None
                self.assert_status(
                    sentence, "A1", PASS, session_terms=session_terms
                )

    def test_required_a2_sentences(self):
        sentences = (
            "Ich bleibe zu Hause, weil ich krank bin.",
            "Gestern habe ich einen Film gesehen.",
        )
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                self.assert_status(sentence, "A2", PASS)

    def test_advanced_sentences_are_unknown(self):
        sentences = (
            "Wir müssen diese Angelegenheit berücksichtigen.",
            "Die Implementierung erfordert eine umfassende Evaluierung.",
        )
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                self.assert_status(sentence, "A2", UNKNOWN)

    def test_a2_presence_is_not_proof_of_above_a1(self):
        result = self.assert_status("Ich komme, weil ich Zeit habe.", "A1", UNKNOWN)
        weil = next(token for token in result["tokens"] if token["token"] == "weil")
        self.assertEqual(weil["classification"], UNVERIFIED)
        self.assertEqual(weil["reason"], "unknown")

    def test_inflection_uses_lemmas(self):
        result = self.assert_status(
            "Ich spreche mit meinen Freunden über ein kleines Haus.", "A1", PASS
        )
        reasons = {token["token"]: token["reason"] for token in result["tokens"]}
        self.assertEqual(reasons["meinen"], "lemma")
        self.assertEqual(reasons["Freunden"], "lemma")
        self.assertEqual(reasons["kleines"], "lemma")

    def test_contraction(self):
        result = self.assert_status(
            "Anna fährt zum Bahnhof.", "A1", PASS, session_terms={"Anna"}
        )
        zum = next(token for token in result["tokens"] if token["token"] == "zum")
        self.assertEqual(zum["reason"], "contraction")

    def test_named_entity_is_not_just_capitalization(self):
        anna = self.assert_status("Anna wohnt hier.", "A1", UNKNOWN)
        anna_token = next(token for token in anna["tokens"] if token["token"] == "Anna")
        self.assertEqual(anna_token["classification"], UNVERIFIED)

        unknown_noun = self.assert_status("Quantencomputer sind interessant.", "A2", UNKNOWN)
        quantum = next(
            token for token in unknown_noun["tokens"] if token["token"] == "Quantencomputer"
        )
        self.assertEqual(quantum["reason"], "unknown")

    def test_explicit_session_term(self):
        result = self.assert_status(
            "Praavars wohnt hier.", "A1", PASS, session_terms={"Praavars"}
        )
        token = next(token for token in result["tokens"] if token["token"] == "Praavars")
        self.assertEqual(token["reason"], "session_term")
        self.assertEqual(token["classification"], EXEMPT)

    def test_separable_verb(self):
        result = self.assert_status("Ich stehe auf.", "A1", PASS)
        tokens = {token["token"]: token for token in result["tokens"]}
        self.assertEqual(tokens["stehe"]["normalized_to"], "aufstehen")
        self.assertEqual(tokens["auf"]["normalized_to"], "aufstehen")

    def test_numbers_and_punctuation(self):
        result = self.assert_status("Ich habe 2 Freunde.", "A1", PASS)
        number = next(token for token in result["tokens"] if token["token"] == "2")
        self.assertEqual(number["reason"], "number")
        self.assertEqual(number["classification"], EXEMPT)

    def test_function_word_policy(self):
        result = self.assert_status(
            "Diese Tasche gehört mir und dieses Buch gehört dir.", "A1", PASS
        )
        reasons = {token["token"]: token["reason"] for token in result["tokens"]}
        self.assertEqual(reasons["Diese"], "function word")
        self.assertEqual(reasons["dieses"], "function word")

    def test_verified_source_artifacts(self):
        self.assert_status("Unser Zimmer ist unten.", "A1", PASS)

    def test_clear_reflexive_entries_are_usable(self):
        self.assert_status("Sie interessiert sich für Musik.", "A2", PASS)
        self.assert_status("Wir treffen uns am Montag.", "A2", PASS)

    def test_digital_time_and_currency(self):
        result = self.assert_status("Der Film beginnt um 20:15 Uhr.", "A2", PASS)
        time = next(token for token in result["tokens"] if token["token"] == "20:15")
        self.assertEqual(time["reason"], "number")
        self.assert_status("Das kostet 12,50 Euro.", "A1", PASS)

    def test_additional_contraction_is_audited(self):
        result = self.assert_status("Das Geschenk ist fürs Kind.", "A2", PASS)
        contraction = next(token for token in result["tokens"] if token["token"] == "fürs")
        self.assertEqual(contraction["reason"], "contraction")

    def test_narrow_irregular_lemma_corrections(self):
        self.assert_status("Möchtest du Äpfel?", "A1", PASS)
        self.assert_status("Kannst du mir helfen?", "A1", PASS)

    def test_conservative_compound_decomposition(self):
        cases = {
            "Der Hauptbahnhof ist hier.": ["haupt-", "bahnhof"],
            "Die Waschmaschine ist kaputt.": ["waschen", "maschine"],
            "Mein Lieblingsfilm ist lustig.": ["lieblings-", "film"],
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence):
                result = self.assert_status(sentence, "A2", PASS)
                compound = next(
                    token for token in result["tokens"] if token["reason"] == "compound"
                )
                self.assertEqual(compound["decomposition"], expected)

    def test_weak_or_ambiguous_compounds_remain_unknown(self):
        for sentence in (
            "Der Fahrradschlüssel liegt hier.",
            "Die Datenschutzgrundverordnung ist wichtig.",
            "Der Quantencomputer ist neu.",
        ):
            with self.subTest(sentence=sentence):
                self.assert_status(sentence, "A2", UNKNOWN)

    def test_session_terms_do_not_allow_arbitrary_capitalized_words(self):
        self.assert_status("Praavars wohnt hier.", "A1", UNKNOWN)
        result = self.assert_status(
            "Praavars wohnt hier.", "A1", PASS, session_terms={"Praavars"}
        )
        name = next(token for token in result["tokens"] if token["token"] == "Praavars")
        self.assertEqual(name["reason"], "session_term")
        self.assertEqual(name["classification"], EXEMPT)

    def test_response_diagnostics(self):
        result = validate_vocabulary(
            "Praavars sieht ein Quantenobjekt um 20:15.",
            "A2",
            session_terms={"Praavars"},
        )
        diagnostics = result["diagnostics"]
        self.assertGreater(diagnostics["allowed_token_count"], 0)
        self.assertEqual(diagnostics["unverified_token_count"], 1)
        self.assertEqual(diagnostics["above_level_token_count"], 0)
        self.assertEqual(diagnostics["exempt_token_count"], 2)
        self.assertEqual(diagnostics["unverified_content_words"], ["Quantenobjekt"])
        self.assertGreaterEqual(diagnostics["lexical_coverage"], 0)
        self.assertLessEqual(diagnostics["lexical_coverage"], 1)

        allowed = next(token for token in result["tokens"] if token["token"] == "sieht")
        self.assertEqual(allowed["classification"], ALLOWED)

    def test_invalid_level(self):
        with self.assertRaises(ValueError):
            validate_vocabulary("Hallo", "B1")


if __name__ == "__main__":
    unittest.main()
