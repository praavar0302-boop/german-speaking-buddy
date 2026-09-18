"""Standalone structural checks for GermanSpeakingBuddy responses.

The thresholds come from ``levels.py`` and are GermanSpeakingBuddy product
heuristics. They are not official CEFR thresholds. This module is deliberately
not connected to the chatbot runtime.
"""

from __future__ import annotations

from functools import lru_cache

import spacy

from levels import get_level_policy


PASS = "PASS"
VIOLATION = "VIOLATION"
MODEL_NAME = "de_core_news_sm"


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


def _subordination(sentence) -> tuple[int, int]:
    """Return subordinate-clause count and maximum nesting depth.

    German spaCy marks subordinating conjunctions with POS ``SCONJ`` and
    normally attaches them to the subordinate clause head with dependency
    ``cp``. Counting these markers is more stable than interpreting every
    German dependency label as a clause.
    """
    clause_heads = [
        token.head
        for token in sentence
        if token.pos_ == "SCONJ" and token.dep_ == "cp"
    ]
    head_indexes = {token.i for token in clause_heads}
    maximum_depth = 0
    for head in clause_heads:
        ancestor_indexes = {ancestor.i for ancestor in head.ancestors}
        depth = 1 + len(head_indexes & ancestor_indexes)
        maximum_depth = max(maximum_depth, depth)
    return len(clause_heads), maximum_depth


def _metric(name, observed, limit, violation: bool) -> dict[str, object]:
    return {
        "metric": name,
        "observed": observed,
        "configured_limit": limit,
        "status": VIOLATION if violation else PASS,
    }


def validate_structure(text: str, level: str) -> dict[str, object]:
    """Validate measurable response structure against the selected policy."""
    normalized_level = level.upper()
    limits = get_level_policy(normalized_level)["application_limits"]
    sentence_limit = limits["sentence_length"]
    response_limit = limits["maximum_response_length"]

    doc = _load_nlp()(text)
    sentences = [sentence for sentence in doc.sents if _word_count(sentence)]
    words_per_sentence = [_word_count(sentence) for sentence in sentences]
    subordinate_counts = []
    subordination_depths = []
    for sentence in sentences:
        count, depth = _subordination(sentence)
        subordinate_counts.append(count)
        subordination_depths.append(depth)

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
    status = VIOLATION if any(item["status"] == VIOLATION for item in metrics) else PASS

    return {
        "status": status,
        "level": normalized_level,
        "text": text,
        "metrics": metrics,
        "note": (
            "Limits are GermanSpeakingBuddy application heuristics, "
            "not official CEFR thresholds."
        ),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Validate response structure")
    parser.add_argument("text")
    parser.add_argument("--level", choices=("A1", "A2"), default="A1")
    args = parser.parse_args()
    print(json.dumps(validate_structure(args.text, args.level), ensure_ascii=False, indent=2))
