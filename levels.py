"""Practical language boundaries for German Speaking Buddy.

CEFR describes communicative proficiency, but it does not publish exhaustive
German grammar or vocabulary whitelists. The linguistic policies below are
deliberately conservative application guardrails, not official CEFR rules.

The application_limits values are GermanSpeakingBuddy product-level enforcement
heuristics. They are measurable defaults for this application, not official
CEFR thresholds.
"""


COMMON_MODAL_LEMMAS = [
    "dürfen",
    "können",
    "mögen",
    "müssen",
    "sollen",
    "wollen",
    "möchten",
]


LEVEL_POLICIES = {
    "A1": {
        "maximum_level": "A1",
        "linguistic_policy": {
            "communicative_abilities": [
                "Handle very familiar, concrete everyday exchanges.",
                "Introduce oneself and ask or answer simple personal questions.",
                "Express basic needs, likes, dislikes, possession, time, and place.",
                "Understand and give short, direct instructions or descriptions.",
            ],
            "allowed_grammar": [
                "Simple present tense with common regular and irregular verbs.",
                "sein, haben, common modal verbs, and möchten in common uses.",
                "Statements with normal verb-second word order.",
                "Yes/no questions, W-questions, and simple imperatives.",
                "Nominative and accusative; dative only in common basic patterns.",
                "Basic articles, possessives, personal pronouns, and negation with nicht/kein.",
                "Common separable verbs and simple adjective use.",
                "Present perfect for frequent everyday verbs in simple sentences.",
            ],
            "structures_to_avoid": [
                "Nested or chained subordinate clauses.",
                "Relative clauses and complex infinitive constructions.",
                "Productive passive voice, genitive constructions, and participial modifiers.",
                "Konjunktiv I or II beyond fixed polite forms such as möchte.",
                "Plusquamperfekt, Futur II, and formal indirect speech.",
                "Dense idioms, abstract phrasing, and uncommon word-order patterns.",
            ],
            "connectors": [
                "und",
                "aber",
                "oder",
                "denn",
                "auch",
                "dann",
                "danach",
                "zuerst",
            ],
            "tense_expectations": [
                "Prefer Präsens.",
                "Use Perfekt only for simple, familiar past events.",
                "Allow common Präteritum forms such as war and hatte when natural.",
                "Express future time mainly with Präsens plus a time expression.",
            ],
            "vocabulary_domains": [
                "personal information, family, and friends",
                "home and simple daily routines",
                "food, drink, shopping, and prices",
                "numbers, dates, time, and weather",
                "school, basic work, and common hobbies",
                "local places, simple directions, and transport",
                "basic health needs and appointments",
            ],
            "conversation_behaviour": [
                "Be friendly, patient, concrete, and predictable.",
                "Ask no more than one simple question at a time.",
                "Prefer common words and repeat or rephrase when helpful.",
                "Use context clues instead of long explanations.",
                "Never intentionally introduce language above A1.",
            ],
        },
        # Product heuristics used by GermanSpeakingBuddy, not official CEFR limits.
        "application_limits": {
            "sentence_length": {
                "preferred": "Aim for roughly 5-12 words per sentence.",
                "maximum": "Normally do not exceed 12 words per sentence.",
                "preferred_min_words": 5,
                "preferred_max_words": 12,
                "maximum_words": 12,
            },
            "maximum_response_length": {
                "sentences": "Usually 2-4 short sentences.",
                "words": "Usually no more than about 45 German words.",
                "maximum_sentences": 4,
                "maximum_words": 45,
            },
            "subordination_complexity_limits": [
                "Use mainly one-clause sentences.",
                "Occasionally join two short main clauses with an allowed connector.",
                "Avoid nested clauses and keep word order predictable.",
            ],
            "maximum_subordination_depth": 0,
            "maximum_subordinate_clauses_per_sentence": 0,
            "language_features": {
                "allowed_subordinate_connectors": [],
                "unlisted_subordinate_connector_result": "VIOLATION",
                "relative_clauses": "avoid",
                "relative_clause_result": "VIOLATION",
                "allowed_tense_patterns": ["present", "perfect"],
                "common_preterite_lemmas": ["sein", "haben"],
                "uncommon_preterite_result": "WARNING",
                "advanced_tense_patterns": ["pluperfect", "future_perfect"],
                "advanced_tense_result": "VIOLATION",
                "allowed_modal_lemmas": COMMON_MODAL_LEMMAS,
                "zu_infinitive": "simple forms are uncertain; avoid complex forms",
                "simple_zu_infinitive_result": "WARNING",
                "multiple_zu_infinitive_result": "WARNING",
                "passive": "avoid productive passive voice",
                "simple_passive_result": "VIOLATION",
                "advanced_passive_result": "VIOLATION",
            },
            "other_measurable_limits": [
                "Ask no more than one question in each response.",
            ],
        },
    },
    "A2": {
        "maximum_level": "A2",
        "linguistic_policy": {
            "communicative_abilities": [
                "Use all A1 abilities with a little more independence and detail.",
                "Manage routine exchanges about daily life, travel, work, and services.",
                "Describe experiences, plans, preferences, surroundings, and simple reasons.",
                "Follow and maintain a short conversation on familiar topics.",
            ],
            "allowed_grammar": [
                "All grammar allowed by the A1 policy.",
                "Präsens, common Perfekt, and frequent Präteritum forms.",
                "Basic subordinate clauses with weil, dass, wenn, and ob.",
                "Common reflexive verbs and verbs with accusative or dative objects.",
                "Common two-way prepositions and basic location/direction distinctions.",
                "Comparative and superlative forms for familiar descriptions.",
                "Simple adjective endings in frequent, clear patterns.",
                "Simple infinitive constructions with zu and common polite würde forms.",
            ],
            "structures_to_avoid": [
                "Multiple nested subordinate clauses or long clause chains.",
                "Complex relative clauses and compressed participial constructions.",
                "Advanced passive forms, especially passive with modal or perfect constructions.",
                "Konjunktiv I and extended Konjunktiv II for hypothetical or indirect discourse.",
                "Plusquamperfekt and Futur II unless briefly required for comprehension.",
                "Abstract academic vocabulary, literary syntax, and dense idiomatic language.",
            ],
            "connectors": [
                "All A1 connectors",
                "weil",
                "dass",
                "wenn",
                "deshalb",
                "trotzdem",
                "also",
                "später",
                "zum Beispiel",
            ],
            "tense_expectations": [
                "Use Präsens freely for current situations and plans.",
                "Use Perfekt as the normal conversational past.",
                "Use Präteritum mainly for sein, haben, modal verbs, and other frequent forms.",
                "Express plans with Präsens or simple werden + infinitive when useful.",
            ],
            "vocabulary_domains": [
                "All A1 vocabulary domains",
                "travel, accommodation, and everyday services",
                "work tasks, education, and future plans",
                "past experiences and simple personal stories",
                "health, exercise, and everyday wellbeing",
                "media, technology, clothing, and leisure",
                "simple opinions, comparisons, reasons, and choices",
            ],
            "conversation_behaviour": [
                "Retain the supportive, concrete behaviour required at A1.",
                "Encourage slightly longer answers without demanding complex language.",
                "Ask one clear question at a time, with occasional simple follow-ups.",
                "Rephrase at A1 or simpler A2 when the learner appears unsure.",
                "Use A1 and A2 language only; never intentionally exceed A2.",
            ],
        },
        # Product heuristics used by GermanSpeakingBuddy, not official CEFR limits.
        "application_limits": {
            "sentence_length": {
                "preferred": "Aim for roughly 6-16 words per sentence.",
                "maximum": "Normally do not exceed 16 words per sentence.",
                "preferred_min_words": 6,
                "preferred_max_words": 16,
                "maximum_words": 16,
            },
            "maximum_response_length": {
                "sentences": "Usually 3-6 short or medium-length sentences.",
                "words": "Usually no more than about 80 German words.",
                "maximum_sentences": 6,
                "maximum_words": 80,
            },
            "subordination_complexity_limits": [
                "Mix short main clauses with occasional simple subordinate clauses.",
                "Use at most one level of subordination and avoid nesting.",
                "Keep references explicit and word order easy to follow.",
            ],
            "maximum_subordination_depth": 1,
            "maximum_subordinate_clauses_per_sentence": 1,
            "language_features": {
                "allowed_subordinate_connectors": ["weil", "dass", "wenn", "ob"],
                "unlisted_subordinate_connector_result": "WARNING",
                "relative_clauses": "allow only simple, non-nested forms",
                "relative_clause_result": "PASS",
                "allowed_tense_patterns": ["present", "perfect", "preterite"],
                "common_preterite_lemmas": [
                    "sein",
                    "haben",
                    *COMMON_MODAL_LEMMAS,
                ],
                "uncommon_preterite_result": "PASS",
                "advanced_tense_patterns": ["pluperfect", "future_perfect"],
                "advanced_tense_result": "WARNING",
                "allowed_modal_lemmas": COMMON_MODAL_LEMMAS,
                "zu_infinitive": "allow simple forms",
                "simple_zu_infinitive_result": "PASS",
                "multiple_zu_infinitive_result": "WARNING",
                "passive": "avoid advanced passive forms",
                "simple_passive_result": "PASS",
                "advanced_passive_result": "WARNING",
            },
            "other_measurable_limits": [
                "Ask no more than one main question in each response.",
            ],
        },
    },
}


def get_level_policy(level):
    """Return the policy for a supported learner level."""
    try:
        return LEVEL_POLICIES[level.upper()]
    except (AttributeError, KeyError) as error:
        supported_levels = ", ".join(LEVEL_POLICIES)
        raise ValueError(
            f"Unsupported learner level: {level!r}. Choose from {supported_levels}."
        ) from error


def format_level_policy(level):
    """Format the complete linguistic policy and application limits for the model."""
    policy = get_level_policy(level)
    linguistic_policy = policy["linguistic_policy"]
    application_limits = policy["application_limits"]
    lines = [
        f"LEARNER LEVEL POLICY — HARD MAXIMUM: {policy['maximum_level']}",
        (
            "The linguistic policy is a conservative application guardrail, "
            "not an exhaustive official CEFR grammar or vocabulary list."
        ),
    ]

    linguistic_sections = {
        "communicative_abilities": "Communicative abilities",
        "allowed_grammar": "Allowed grammar",
        "structures_to_avoid": "Structures to avoid as above-level language",
        "connectors": "Allowed/common connectors",
        "tense_expectations": "Tense expectations",
        "vocabulary_domains": "Common vocabulary and topic domains",
        "conversation_behaviour": "Conversation behaviour",
    }

    lines.append("\nLINGUISTIC POLICY:")
    for key, heading in linguistic_sections.items():
        lines.append(f"\n{heading}:")
        lines.extend(f"- {item}" for item in linguistic_policy[key])

    lines.extend(
        [
            "\nAPPLICATION LIMITS:",
            (
                "These are GermanSpeakingBuddy product-level enforcement "
                "heuristics, not official CEFR thresholds."
            ),
            "\nPreferred/max sentence length:",
            f"- Preferred: {application_limits['sentence_length']['preferred']}",
            f"- Maximum: {application_limits['sentence_length']['maximum']}",
            "\nMaximum response length:",
        ]
    )
    lines.extend(
        [
            f"- Sentences: {application_limits['maximum_response_length']['sentences']}",
            f"- Words: {application_limits['maximum_response_length']['words']}",
        ]
    )

    lines.append("\nSubordination/complexity limits:")
    lines.extend(
        f"- {item}"
        for item in application_limits["subordination_complexity_limits"]
    )

    lines.append("\nOther measurable limits:")
    lines.extend(
        f"- {item}" for item in application_limits["other_measurable_limits"]
    )

    return "\n".join(lines)
