"""Standalone language-level checks for GermanSpeakingBuddy responses.

The validator checks sentence structure and grammar complexity using thresholds
from ``levels.py``. These are GermanSpeakingBuddy product heuristics, not
official CEFR thresholds. This module is deliberately not connected to the
chatbot runtime.
"""

from __future__ import annotations

from functools import lru_cache

import spacy

from levels import get_level_policy


PASS = "PASS"
VIOLATION = "VIOLATION"
WARNING = "WARNING"
MODEL_NAME = "de_core_news_sm"

# Narrow fallbacks for common forms that the small German model occasionally
# tags as adjectives or adverbs instead of modal verbs.
MODAL_LEMMA_FALLBACKS = {
    "muss": "müssen",
    "musst": "müssen",
    "müsst": "müssen",
}


@lru_cache(maxsize=1)
def _load_nlp():
    try:
        return spacy.load(MODEL_NAME)
    except OSError as error:
        raise RuntimeError(
            f"spaCy model {MODEL_NAME!r} is not installed. "
            "Run: python -m spacy download de_core_news_sm"
        ) from error


def _word_count(tokens) -> int:
    """Count word-like tokens while excluding punctuation and whitespace."""
    return sum(token.is_alpha or token.like_num for token in tokens)


def _clause_analysis(sentence) -> dict[str, object]:
    """Describe explicit subordinate and relative clauses once.

    German spaCy marks subordinating conjunctions with POS ``SCONJ`` and
    normally attaches them to the subordinate clause head with dependency
    ``cp``. Relative clauses normally use dependency ``rc`` and a relative
    pronoun. Both feed the existing clause-count and nesting metrics.
    """
    clauses = [
        {
            "type": "subordinate",
            "connector": token.lemma_.casefold(),
            "head": token.head,
        }
        for token in sentence
        if token.pos_ == "SCONJ" and token.dep_ == "cp"
    ]
    relative_heads = {
        token.i: token for token in sentence if token.dep_ == "rc"
    }
    relative_heads.update(
        {
            token.head.i: token.head
            for token in sentence
            if token.morph.get("PronType") == ["Rel"]
            and token.head.i >= sentence.start
            and token.head.i < sentence.end
        }
    )
    clauses.extend(
        {"type": "relative", "connector": None, "head": head}
        for head in relative_heads.values()
    )

    head_indexes = {clause["head"].i for clause in clauses}
    maximum_depth = 0
    for clause in clauses:
        head = clause["head"]
        ancestor_indexes = {ancestor.i for ancestor in head.ancestors}
        depth = 1 + len(head_indexes & ancestor_indexes)
        clause["depth"] = depth
        clause["head_text"] = head.text
        del clause["head"]
        maximum_depth = max(maximum_depth, depth)
    return {
        "clauses": clauses,
        "count": len(clauses),
        "maximum_depth": maximum_depth,
    }


def _metric(name, observed, limit, violation: bool) -> dict[str, object]:
    return {
        "metric": name,
        "observed": observed,
        "configured_limit": limit,
        "status": VIOLATION if violation else PASS,
    }


def _feature(name, observed, policy, status=PASS) -> dict[str, object]:
    return {
        "feature": name,
        "observed": observed,
        "configured_policy": policy,
        "status": status,
    }


def _has_descendant(token, *, lemmas=None, verb_form=None) -> bool:
    for descendant in token.subtree:
        if descendant.i == token.i:
            continue
        if lemmas and descendant.lemma_.casefold() in lemmas:
            return True
        if verb_form and verb_form in descendant.morph.get("VerbForm"):
            return True
    return False


def _tense_patterns(sentence) -> list[dict[str, object]]:
    """Return conservative tense-pattern observations for finite verbs."""
    observations = []
    for token in sentence:
        if "Fin" not in token.morph.get("VerbForm"):
            continue

        lemma = token.lemma_.casefold()
        tense = token.morph.get("Tense")
        has_participle = _has_descendant(token, verb_form="Part")
        has_infinitive_auxiliary = _has_descendant(token, lemmas={"haben", "sein"})

        if lemma == "werden" and has_participle and has_infinitive_auxiliary:
            pattern = "future_perfect"
        elif lemma in {"haben", "sein"} and has_participle and "Past" in tense:
            pattern = "pluperfect"
        elif lemma in {"haben", "sein"} and has_participle and "Pres" in tense:
            pattern = "perfect"
        elif "Past" in tense:
            pattern = "preterite"
        elif "Pres" in tense:
            pattern = "present"
        else:
            continue

        observations.append({"pattern": pattern, "verb": token.text, "lemma": lemma})
    return observations


def _modal_verbs(sentence, allowed_lemmas) -> list[dict[str, str]]:
    allowed = set(allowed_lemmas)
    results = []
    for token in sentence:
        surface = token.text.casefold()
        lemma = MODAL_LEMMA_FALLBACKS.get(surface, token.lemma_.casefold())
        if lemma in allowed or token.tag_.startswith("VM"):
            results.append({"token": token.text, "lemma": lemma})
    return results


def _zu_infinitives(sentence) -> list[dict[str, str]]:
    return [
        {"zu": token.text, "infinitive": token.head.text}
        for token in sentence
        if token.tag_ == "PTKZU"
        and token.head.pos_ in {"VERB", "AUX"}
        and "Inf" in token.head.morph.get("VerbForm")
    ]


def _passive_patterns(sentence, modal_lemmas) -> list[dict[str, object]]:
    """Find clear werden + participle passive-like auxiliary chains."""
    participles = [
        token
        for token in sentence
        if token.pos_ == "VERB" and "Part" in token.morph.get("VerbForm")
    ]
    if not participles:
        return []

    werden = [token for token in sentence if token.lemma_.casefold() == "werden"]
    if not werden:
        return []

    has_modal = bool(_modal_verbs(sentence, modal_lemmas))
    has_worden = any(token.text.casefold() == "worden" for token in sentence)
    kind = "advanced" if has_modal or has_worden else "simple"
    return [
        {
            "kind": kind,
            "auxiliary": [token.text for token in werden],
            "participles": [token.text for token in participles],
        }
    ]


def validate_structure(text: str, level: str) -> dict[str, object]:
    """Validate measurable response structure against the selected policy."""
    normalized_level = level.upper()
    limits = get_level_policy(normalized_level)["application_limits"]
    sentence_limit = limits["sentence_length"]
    response_limit = limits["maximum_response_length"]
    feature_policy = limits["language_features"]

    doc = _load_nlp()(text)
    sentences = [sentence for sentence in doc.sents if _word_count(sentence)]
    words_per_sentence = [_word_count(sentence) for sentence in sentences]
    subordinate_counts = []
    subordination_depths = []
    clause_analyses = []
    for sentence in sentences:
        analysis = _clause_analysis(sentence)
        clause_analyses.append(analysis)
        subordinate_counts.append(analysis["count"])
        subordination_depths.append(analysis["maximum_depth"])

    maximum_sentence_words = max(words_per_sentence, default=0)
    maximum_subordinate_count = max(subordinate_counts, default=0)
    maximum_subordination_depth = max(subordination_depths, default=0)

    metrics = [
        _metric(
            "sentence_count",
            len(sentences),
            response_limit["maximum_sentences"],
            len(sentences) > response_limit["maximum_sentences"],
        ),
        _metric(
            "words_per_sentence",
            words_per_sentence,
            {
                "preferred_min": sentence_limit["preferred_min_words"],
                "preferred_max": sentence_limit["preferred_max_words"],
                "maximum": sentence_limit["maximum_words"],
            },
            maximum_sentence_words > sentence_limit["maximum_words"],
        ),
        _metric(
            "total_response_word_count",
            _word_count(doc),
            response_limit["maximum_words"],
            _word_count(doc) > response_limit["maximum_words"],
        ),
        _metric(
            "subordinate_clauses_per_sentence",
            subordinate_counts,
            limits["maximum_subordinate_clauses_per_sentence"],
            maximum_subordinate_count
            > limits["maximum_subordinate_clauses_per_sentence"],
        ),
        _metric(
            "subordination_depth",
            maximum_subordination_depth,
            limits["maximum_subordination_depth"],
            maximum_subordination_depth > limits["maximum_subordination_depth"],
        ),
    ]

    features = []
    allowed_connectors = set(feature_policy["allowed_subordinate_connectors"])
    for sentence_number, analysis in enumerate(clause_analyses, start=1):
        for clause in analysis["clauses"]:
            observed = {"sentence": sentence_number, **clause}
            if clause["type"] == "relative":
                features.append(
                    _feature(
                        "relative_clause",
                        observed,
                        feature_policy["relative_clauses"],
                        feature_policy["relative_clause_result"],
                    )
                )
                continue

            connector = clause["connector"]
            if connector in allowed_connectors:
                status = PASS
            else:
                status = feature_policy["unlisted_subordinate_connector_result"]
            features.append(
                _feature(
                    "subordinate_connector",
                    observed,
                    sorted(allowed_connectors),
                    status,
                )
            )

    for sentence_number, sentence in enumerate(sentences, start=1):
        for tense in _tense_patterns(sentence):
            pattern = tense["pattern"]
            if pattern in feature_policy["advanced_tense_patterns"]:
                status = feature_policy["advanced_tense_result"]
            elif (
                pattern == "preterite"
                and tense["lemma"] not in feature_policy["common_preterite_lemmas"]
            ):
                status = feature_policy["uncommon_preterite_result"]
            else:
                status = PASS
            features.append(
                _feature(
                    "verb_tense",
                    {"sentence": sentence_number, **tense},
                    feature_policy["allowed_tense_patterns"],
                    status,
                )
            )

        modals = _modal_verbs(sentence, feature_policy["allowed_modal_lemmas"])
        if modals:
            features.append(
                _feature(
                    "modal_verbs",
                    {"sentence": sentence_number, "verbs": modals},
                    feature_policy["allowed_modal_lemmas"],
                )
            )

        infinitives = _zu_infinitives(sentence)
        if infinitives:
            result_key = (
                "simple_zu_infinitive_result"
                if len(infinitives) == 1
                else "multiple_zu_infinitive_result"
            )
            features.append(
                _feature(
                    "zu_infinitive",
                    {"sentence": sentence_number, "constructions": infinitives},
                    feature_policy["zu_infinitive"],
                    feature_policy[result_key],
                )
            )

        for passive in _passive_patterns(
            sentence, feature_policy["allowed_modal_lemmas"]
        ):
            result_key = f"{passive['kind']}_passive_result"
            features.append(
                _feature(
                    "passive",
                    {"sentence": sentence_number, **passive},
                    feature_policy["passive"],
                    feature_policy[result_key],
                )
            )

    results = [*metrics, *features]
    if any(item["status"] == VIOLATION for item in results):
        status = VIOLATION
    elif any(item["status"] == WARNING for item in results):
        status = WARNING
    else:
        status = PASS

    return {
        "status": status,
        "level": normalized_level,
        "text": text,
        "metrics": metrics,
        "features": features,
        "note": (
            "Limits are GermanSpeakingBuddy application heuristics, "
            "not official CEFR thresholds."
        ),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Validate response language level")
    parser.add_argument("text")
    parser.add_argument("--level", choices=("A1", "A2"), default="A1")
    args = parser.parse_args()
    print(json.dumps(validate_structure(args.text, args.level), ensure_ascii=False, indent=2))
