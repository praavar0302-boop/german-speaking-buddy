"""Standalone decisions for validated GermanSpeakingBuddy responses.

This module combines the existing vocabulary and language-level validator
results. It is deliberately not connected to the chatbot runtime yet.
"""

from __future__ import annotations

from typing import Iterable

from language_validator import VIOLATION, WARNING, validate_structure
from validator import (
    ABOVE_LEVEL,
    ALLOWED,
    EXEMPT,
    UNVERIFIED,
    validate_vocabulary,
)


DISPLAY = "DISPLAY"
DISPLAY_AND_RECORD = "DISPLAY_AND_RECORD"
REGENERATE = "REGENERATE"
FALLBACK = "FALLBACK"

MAX_REGENERATION_ATTEMPTS = 2


def _vocabulary_summary(result: dict[str, object]) -> dict[str, object]:
    tokens = result["tokens"]
    diagnostics = result["diagnostics"]
    allowed_content = sum(
        token["is_content"] and token["classification"] == ALLOWED
        for token in tokens
    )
    unverified_content = [
        token["token"]
        for token in tokens
        if token["is_content"] and token["classification"] == UNVERIFIED
    ]
    exempt_only = bool(tokens) and all(
        token["classification"] == EXEMPT for token in tokens
    )

    return {
        "allowed_token_count": diagnostics["allowed_token_count"],
        "unverified_token_count": diagnostics["unverified_token_count"],
        "above_level_token_count": diagnostics["above_level_token_count"],
        "exempt_token_count": diagnostics["exempt_token_count"],
        "allowed_content_word_count": allowed_content,
        "unverified_content_word_count": len(unverified_content),
        "lexical_coverage": diagnostics["lexical_coverage"],
        "unverified_content_words": unverified_content,
        "exempt_only": exempt_only,
    }


def _language_summary(result: dict[str, object]) -> dict[str, object]:
    checks = [*result["metrics"], *result["features"]]
    warnings = [check for check in checks if check["status"] == WARNING]
    violations = [check for check in checks if check["status"] == VIOLATION]
    return {
        "status": result["status"],
        "warning_count": len(warnings),
        "violation_count": len(violations),
        "warnings": warnings,
        "violations": violations,
    }


def _feedback_items(vocabulary, language) -> dict[str, object]:
    return {
        "uncertain_vocabulary": list(vocabulary["unverified_content_words"]),
        "language_warnings": list(language["warnings"]),
    }


def _base_decision(
    text: str,
    level: str,
    attempt: int,
    vocabulary: dict[str, object],
    language: dict[str, object],
) -> dict[str, object]:
    reasons = []
    unverified = vocabulary["unverified_content_word_count"]
    allowed = vocabulary["allowed_content_word_count"]
    warning_count = language["warning_count"]

    if language["status"] == VIOLATION or language["violation_count"]:
        action = REGENERATE
        reasons.append("LANGUAGE_VIOLATION")
    elif warning_count > 1:
        action = REGENERATE
        reasons.append("MULTIPLE_LANGUAGE_WARNINGS")
    elif vocabulary["exempt_only"]:
        action = DISPLAY
        reasons.append("EXEMPT_ONLY_RESPONSE")
    elif unverified == 0:
        action = DISPLAY
        reasons.append("NO_UNVERIFIED_CONTENT_WORDS")
        if warning_count == 1:
            reasons.append("ONE_LANGUAGE_WARNING")
    elif unverified == 1 and allowed >= 1:
        action = DISPLAY_AND_RECORD
        reasons.append("ONE_UNVERIFIED_WITH_ALLOWED_CONTENT")
        if warning_count == 1:
            reasons.append("ONE_LANGUAGE_WARNING")
    elif unverified == 1:
        action = REGENERATE
        reasons.append("ONE_UNVERIFIED_WITHOUT_ALLOWED_CONTENT")
    elif unverified == 2 and language["status"] == "PASS" and allowed >= 4:
        action = DISPLAY_AND_RECORD
        reasons.append("TWO_UNVERIFIED_WITH_SUFFICIENT_ALLOWED_CONTENT")
    elif unverified == 2:
        action = REGENERATE
        reasons.append("TWO_UNVERIFIED_INSUFFICIENT_EVIDENCE")
    else:
        action = REGENERATE
        reasons.append("THREE_OR_MORE_UNVERIFIED_CONTENT_WORDS")

    return {
        "action": action,
        "level": level.upper(),
        "attempt": attempt,
        "selected_attempt": attempt,
        "text": text,
        "reason_codes": reasons,
        "vocabulary": vocabulary,
        "language": language,
        "record_for_feedback": _feedback_items(vocabulary, language),
    }


def _candidate_rank(candidate: dict[str, object]) -> tuple:
    language = candidate["language"]
    vocabulary = candidate["vocabulary"]
    coverage = vocabulary["lexical_coverage"]
    coverage = coverage if coverage is not None else -1.0
    return (
        0 if language["status"] == "PASS" else 1,
        language["warning_count"],
        vocabulary["unverified_content_word_count"],
        -vocabulary["allowed_content_word_count"],
        -coverage,
    )


def _resolve_exhausted_attempts(candidates, level, attempt):
    safe_candidates = [
        candidate
        for candidate in candidates
        if candidate["language"]["status"] != VIOLATION
        and not candidate["language"]["violation_count"]
    ]
    if not safe_candidates:
        latest = candidates[-1]
        return {
            "action": FALLBACK,
            "level": level.upper(),
            "attempt": attempt,
            "selected_attempt": None,
            "text": None,
            "reason_codes": ["RETRIES_EXHAUSTED", "NO_SAFE_CANDIDATE"],
            "vocabulary": latest["vocabulary"],
            "language": latest["language"],
            "record_for_feedback": {
                "uncertain_vocabulary": [],
                "language_warnings": [],
            },
        }

    selected = min(safe_candidates, key=_candidate_rank)
    has_feedback = bool(
        selected["record_for_feedback"]["uncertain_vocabulary"]
        or selected["record_for_feedback"]["language_warnings"]
    )
    return {
        **selected,
        "action": DISPLAY_AND_RECORD if has_feedback else DISPLAY,
        "attempt": attempt,
        "selected_attempt": selected["attempt"],
        "reason_codes": [
            "RETRIES_EXHAUSTED",
            "SAFEST_CANDIDATE_SELECTED",
            *selected["reason_codes"],
        ],
    }


def decide_from_results(
    text: str,
    level: str,
    vocabulary_result: dict[str, object],
    language_result: dict[str, object],
    *,
    attempt: int = 0,
    previous_candidates: Iterable[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Decide what to do with one candidate using validator results."""
    if attempt < 0 or attempt > MAX_REGENERATION_ATTEMPTS:
        raise ValueError(
            f"attempt must be between 0 and {MAX_REGENERATION_ATTEMPTS}"
        )

    current = _base_decision(
        text,
        level,
        attempt,
        _vocabulary_summary(vocabulary_result),
        _language_summary(language_result),
    )
    if current["action"] != REGENERATE or attempt < MAX_REGENERATION_ATTEMPTS:
        return current

    candidates = [*(previous_candidates or ()), current]
    return _resolve_exhausted_attempts(candidates, level, attempt)


def decide_response(
    text: str,
    level: str,
    *,
    attempt: int = 0,
    previous_candidates: Iterable[dict[str, object]] | None = None,
    session_terms: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run both standalone validators and decide how to handle the response."""
    vocabulary_result = validate_vocabulary(text, level, session_terms=session_terms)
    language_result = validate_structure(text, level)
    return decide_from_results(
        text,
        level,
        vocabulary_result,
        language_result,
        attempt=attempt,
        previous_candidates=previous_candidates,
    )
