"""Standalone deterministic vocabulary checks for GermanSpeakingBuddy.

This module is intentionally not connected to the Streamlit application yet.
It combines compiled Goethe vocabulary data, spaCy German lemmas, and a small
set of explicit rules. Positive evidence, missing evidence, and exemptions are
kept separate so absence from a Goethe list is never treated as proof that a
word is above the selected level.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import spacy


PROJECT_ROOT = Path(__file__).resolve().parent
VOCABULARY_DIR = PROJECT_ROOT / "data" / "vocabulary"
MODEL_NAME = "de_core_news_sm"

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

ALLOWED = "ALLOWED"
ABOVE_LEVEL = "ABOVE_LEVEL"
UNVERIFIED = "UNVERIFIED"
EXEMPT = "EXEMPT"

CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}

CONTRACTIONS = {
    "am": ("an", "dem"),
    "ans": ("an", "das"),
    "aufs": ("auf", "das"),
    "beim": ("bei", "dem"),
    "durchs": ("durch", "das"),
    "fürs": ("für", "das"),
    "im": ("in", "dem"),
    "ins": ("in", "das"),
    "übers": ("über", "das"),
    "ums": ("um", "das"),
    "vom": ("von", "dem"),
    "zum": ("zu", "dem"),
    "zur": ("zu", "der"),
}

CONTRACTION_ARTICLES = {"das", "dem", "der"}
DIGITAL_TIME = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
LINKING_ELEMENTS = ("en", "er", "es", "s", "n")

# Compound-only modifiers are deliberately tiny. "Haupt-" is a transparent,
# common A2 local-place modifier; it is not promoted to general vocabulary.
COMPOUND_ONLY_MODIFIERS = {"A1": set(), "A2": {"haupt"}}

# A1 explicitly allows basic articles, possessives, personal pronouns,
# W-questions, auxiliaries, and common modal verbs. These closed grammatical
# families should not become A2-only merely because a pedagogical word list
# groups or omits an inflected form.
A1_FUNCTION_WORDS = {
    "alle",
    "anderer",
    "beide",
    "dich",
    "dein",
    "der",
    "dieser",
    "dir",
    "du",
    "dürfen",
    "ein",
    "er",
    "es",
    "euch",
    "euer",
    "haben",
    "ich",
    "ihm",
    "ihn",
    "ihnen",
    "ihr",
    "jeder",
    "kein",
    "können",
    "man",
    "mein",
    "mich",
    "mir",
    "möchten",
    "mögen",
    "müssen",
    "sein",
    "sie",
    "sich",
    "sollen",
    "unser",
    "uns",
    "was",
    "wann",
    "warum",
    "welcher",
    "wer",
    "werden",
    "wie",
    "wir",
    "wo",
    "woher",
    "wohin",
    "wollen",
}

# Narrow corrections for observed spaCy misses. Each target is either an
# explicit source lemma or an explicit productive source stem; this is not a
# general morphology engine.
IRREGULAR_LEMMAS = {
    "anders": "ander",
    "äpfel": "apfel",
    "kannst": "können",
    "möchtest": "möchten",
}


def _normalized(text: str) -> str:
    return text.casefold().strip()


@lru_cache(maxsize=1)
def _load_nlp():
    try:
        return spacy.load(MODEL_NAME)
    except OSError as error:
        raise RuntimeError(
            f"spaCy model {MODEL_NAME!r} is not installed. "
            "Run: python -m spacy download de_core_news_sm"
        ) from error


@lru_cache(maxsize=2)
def _load_lexicon(level: str) -> dict[str, set]:
    path = VOCABULARY_DIR / f"{level.lower()}.compiled.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    words: set[str] = set()
    phrases: set[tuple[str, ...]] = set()
    productive_stems: set[str] = set()

    for entry in data["entries"]:
        # Unreviewed compiler output is usable now. Ambiguous records remain in
        # the JSON with provenance, but are not silently promoted to vocabulary.
        if entry["manual_review"]:
            # Productive stems such as "ein-" are explicit source entries. The
            # base is useful with spaCy's lemma "ein", without generating forms.
            if entry["manual_review"] == ["productive stem, not a complete lemma"]:
                stem = _normalized(entry["lemma"]).removesuffix("-")
                words.add(stem)
                productive_stems.add(stem)
            continue

        values = [entry["lemma"], *entry["forms"], *entry["phrases"], *entry["abbreviations"]]
        for value in values:
            if not value:
                continue
            normalized = _normalized(value)
            parts = tuple(normalized.split())
            if len(parts) == 1:
                words.add(normalized)
            else:
                phrases.add(parts)

        # Goethe's word-group section supplies these currency units together.
        if entry["source_entry"] == "1 Euro = 100 Cent":
            words.update({"euro", "cent"})

    if level == "A2":
        # The Goethe A2 source is cumulative, but unioning A1 also prevents a
        # conservatively excluded ambiguous A2 row from losing a clean A1 item.
        a1 = _load_lexicon("A1")
        words.update(a1["words"])
        phrases.update(a1["phrases"])
        productive_stems.update(a1["productive_stems"])

    return {
        "words": words,
        "phrases": phrases,
        "productive_stems": productive_stems,
    }


def _phrase_indexes(doc, phrases: set[tuple[str, ...]]) -> dict[int, str]:
    indexes: dict[int, str] = {}
    lowered = [_normalized(token.text) for token in doc]
    for phrase in phrases:
        size = len(phrase)
        for start in range(len(lowered) - size + 1):
            if tuple(lowered[start : start + size]) == phrase:
                phrase_text = " ".join(phrase)
                for index in range(start, start + size):
                    indexes[index] = phrase_text
    return indexes


def _separable_verbs(doc, words: set[str]) -> dict[int, str]:
    matches: dict[int, str] = {}
    for particle in doc:
        if particle.dep_ != "svp" or particle.head.pos_ not in {"VERB", "AUX"}:
            continue
        combined = _normalized(particle.text + particle.head.lemma_)
        if combined in words:
            matches[particle.i] = combined
            matches[particle.head.i] = combined
    return matches


def _compound_decomposition(
    token,
    level: str,
    lexicon: dict[str, set],
) -> list[str] | None:
    """Return one high-confidence compound analysis, otherwise None.

    Unlinked noun+noun guesses are intentionally rejected. Accepted analyses
    require an explicit productive stem, a tiny compound-only modifier policy,
    a source verb stem, or an unambiguous linking element.
    """
    if token.pos_ != "NOUN" or not token.text.isalpha() or len(token.text) < 7:
        return None

    surface = _normalized(token.text)
    words = lexicon["words"]

    stem_candidates = {
        (f"{stem}-", surface[len(stem) :])
        for stem in lexicon["productive_stems"]
        if surface.startswith(stem)
        and len(surface) > len(stem) + 2
        and surface[len(stem) :] in words
    }
    if len(stem_candidates) == 1:
        return list(next(iter(stem_candidates)))
    if len(stem_candidates) > 1:
        return None

    modifier_candidates = {
        (f"{modifier}-", surface[len(modifier) :])
        for modifier in COMPOUND_ONLY_MODIFIERS[level]
        if surface.startswith(modifier)
        and len(surface) > len(modifier) + 2
        and surface[len(modifier) :] in words
    }
    if len(modifier_candidates) == 1:
        return list(next(iter(modifier_candidates)))
    if len(modifier_candidates) > 1:
        return None

    candidates: set[tuple[str, str]] = set()
    for split in range(3, len(surface) - 2):
        left = surface[:split]
        right = surface[split:]
        if right not in words:
            continue

        # German verb stems frequently form transparent compounds, e.g.
        # wasch- + Maschine. Require the corresponding source infinitive.
        infinitive = f"{left}en"
        if len(left) >= 4 and infinitive in words:
            candidates.add((infinitive, right))

        # Linking elements are accepted only when removing one yields an
        # independently allowed component and the analysis is unique.
        for linker in LINKING_ELEMENTS:
            if left.endswith(linker):
                base = left[: -len(linker)]
                if len(base) >= 3 and base in words:
                    candidates.add((f"{base}+{linker}", right))

    if len(candidates) == 1:
        return list(next(iter(candidates)))
    return None


def validate_vocabulary(
    text: str,
    level: str,
    session_terms: Iterable[str] | None = None,
) -> dict[str, object]:
    """Validate text against compiled A1 or cumulative A2 vocabulary.

    Token classifications distinguish positive level evidence (ALLOWED),
    explicit evidence above the selected level (ABOVE_LEVEL), insufficient
    evidence (UNVERIFIED), and tokens outside vocabulary enforcement (EXEMPT).

    The current data contains positive A1/A2 evidence but no authoritative
    above-A2 inventory. In particular, A2 presence plus A1 absence is only
    insufficient A1 evidence; it is not ABOVE_LEVEL evidence.
    """
    normalized_level = level.upper()
    if normalized_level not in {"A1", "A2"}:
        raise ValueError("level must be 'A1' or 'A2'")

    nlp = _load_nlp()
    selected = _load_lexicon(normalized_level)
    session_words: set[str] = set()
    session_phrases: set[tuple[str, ...]] = set()
    for term in session_terms or ():
        parts = tuple(_normalized(term).split())
        if len(parts) == 1:
            session_words.add(parts[0])
        elif parts:
            session_phrases.add(parts)

    doc = nlp(text)
    selected_phrase_indexes = _phrase_indexes(doc, selected["phrases"])
    session_phrase_indexes = _phrase_indexes(doc, session_phrases)
    separable_verbs = _separable_verbs(doc, selected["words"])

    token_results: list[dict[str, object]] = []
    for token in doc:
        if token.is_space or token.is_punct:
            continue

        surface = _normalized(token.text)
        lemma = IRREGULAR_LEMMAS.get(surface, _normalized(token.lemma_))
        classification = ALLOWED
        reason: str
        normalized_to: str | list[str] | None = None
        decomposition: list[str] | None = None

        if token.like_num or DIGITAL_TIME.fullmatch(surface.rstrip(".")):
            classification = EXEMPT
            reason = "number"
            normalized_to = surface.rstrip(".")
        elif token.i in session_phrase_indexes:
            classification = EXEMPT
            reason = "session_term"
            normalized_to = session_phrase_indexes[token.i]
        elif surface in session_words:
            classification = EXEMPT
            reason = "session_term"
            normalized_to = surface
        elif token.i in selected_phrase_indexes:
            reason = "exact"
            normalized_to = selected_phrase_indexes[token.i]
        elif surface in CONTRACTIONS:
            expansion = CONTRACTIONS[surface]
            normalized_to = list(expansion)
            preposition, article = expansion
            if preposition in selected["words"] and article in CONTRACTION_ARTICLES:
                reason = "contraction"
            else:
                classification = UNVERIFIED
                reason = "unknown"
        elif token.i in separable_verbs:
            reason = "lemma"
            normalized_to = separable_verbs[token.i]
        elif surface in selected["words"]:
            reason = "exact"
            normalized_to = surface
        elif lemma in selected["words"]:
            reason = "lemma"
            normalized_to = lemma
        elif surface in A1_FUNCTION_WORDS or lemma in A1_FUNCTION_WORDS:
            reason = "function word"
            normalized_to = lemma if lemma in A1_FUNCTION_WORDS else surface
        elif decomposition := _compound_decomposition(token, normalized_level, selected):
            reason = "compound"
            normalized_to = surface
        else:
            classification = UNVERIFIED
            reason = "unknown"

        token_results.append(
            {
                "token": token.text,
                "lemma": token.lemma_,
                "classification": classification,
                "reason": reason,
                "normalized_to": normalized_to,
                "decomposition": decomposition,
                "pos": token.pos_,
                "is_content": token.pos_ in CONTENT_POS,
            }
        )

    classifications = {result["classification"] for result in token_results}
    if ABOVE_LEVEL in classifications:
        overall_status = FAIL
    elif UNVERIFIED in classifications:
        overall_status = UNKNOWN
    else:
        overall_status = PASS

    counts = {
        classification: sum(
            result["classification"] == classification for result in token_results
        )
        for classification in (ALLOWED, UNVERIFIED, ABOVE_LEVEL, EXEMPT)
    }
    lexical_tokens = [
        result
        for result in token_results
        if result["is_content"] and result["classification"] != EXEMPT
    ]
    lexical_allowed = sum(
        result["classification"] == ALLOWED for result in lexical_tokens
    )
    lexical_coverage = (
        lexical_allowed / len(lexical_tokens) if lexical_tokens else None
    )
    unverified_content_words = [
        result["token"]
        for result in lexical_tokens
        if result["classification"] == UNVERIFIED
    ]

    return {
        "status": overall_status,
        "level": normalized_level,
        "text": text,
        "tokens": token_results,
        "diagnostics": {
            "allowed_token_count": counts[ALLOWED],
            "unverified_token_count": counts[UNVERIFIED],
            "above_level_token_count": counts[ABOVE_LEVEL],
            "exempt_token_count": counts[EXEMPT],
            "lexical_coverage": lexical_coverage,
            "unverified_content_words": unverified_content_words,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate German vocabulary")
    parser.add_argument("text")
    parser.add_argument("--level", choices=("A1", "A2"), default="A1")
    args = parser.parse_args()
    print(json.dumps(validate_vocabulary(args.text, args.level), ensure_ascii=False, indent=2))
