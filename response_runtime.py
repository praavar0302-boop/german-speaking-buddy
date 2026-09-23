"""Validated response streaming for the live chatbot.

Generated text is buffered until a complete sentence is available. Only text
accepted by the decision layer is yielded for display or saved to history.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Iterable

from decision_layer import (
    DISPLAY,
    DISPLAY_AND_RECORD,
    FALLBACK,
    MAX_REGENERATION_ATTEMPTS,
    REGENERATE,
    decide_response,
)


TYPING_MESSAGE = "GermanSpeakingBuddy tippt …"
MAX_RESPONSE_SENTENCES = 3
FALLBACK_SENTENCE = "Bitte sag das noch einmal."
SENTENCE_BOUNDARY = re.compile(r"[.!?](?:[\"'»”])*(?:\s+|$)")


def timed_model_chunks(chunks, diagnostics):
    """Count only time spent waiting for model stream chunks."""
    source = iter(chunks)
    while True:
        started = time.perf_counter()
        try:
            chunk = next(source)
        except StopIteration:
            diagnostics["model_seconds"] += time.perf_counter() - started
            return
        except Exception:
            diagnostics["model_seconds"] += time.perf_counter() - started
            raise
        diagnostics["model_seconds"] += time.perf_counter() - started
        yield chunk


def first_validated_chunks(chunks, diagnostics):
    """Note when the first displayable, validated chunk becomes ready."""
    for chunk in chunks:
        if diagnostics["first_validated_seconds"] is None:
            diagnostics["first_validated_seconds"] = (
                time.perf_counter() - diagnostics["started_at"]
            )
        yield chunk


def capture_generated_chunks(chunks, diagnostics):
    """Keep consumed model reply text for the server-side turn audit."""
    for chunk in chunks:
        diagnostics["generated_assistant_candidate"] += chunk
        yield chunk


def _decide_timed(decision_fn, text, level, diagnostics, **kwargs):
    started = time.perf_counter()
    try:
        decision = decision_fn(text, level, **kwargs)
        if diagnostics is not None:
            diagnostics.setdefault("decisions", []).append(
                {
                    "candidate": text,
                    "action": decision["action"],
                    "reason_codes": decision.get("reason_codes", []),
                    "unverified_vocabulary": decision.get("vocabulary", {}).get(
                        "unverified_content_words", []
                    ),
                    "language_warnings": decision.get("language", {}).get(
                        "warnings", []
                    ),
                    "language_violations": decision.get("language", {}).get(
                        "violations", []
                    ),
                }
            )
        return decision
    finally:
        if diagnostics is not None:
            diagnostics["validation_seconds"] += time.perf_counter() - started


def iter_sentences(chunks: Iterable[str]):
    """Yield complete sentences from arbitrary streamed text chunks."""
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        while match := SENTENCE_BOUNDARY.search(buffer):
            sentence = buffer[: match.end()].strip()
            buffer = buffer[match.end() :]
            if sentence:
                yield sentence
    if buffer.strip():
        yield buffer.strip()


def _rewrite_instruction(sentence: str, level: str, decision) -> str:
    vocabulary = decision["vocabulary"]["unverified_content_words"]
    structural_problem = any(
        reason in decision["reason_codes"]
        for reason in ("LANGUAGE_VIOLATION", "MULTIPLE_LANGUAGE_WARNINGS")
    )

    if vocabulary and not structural_problem:
        words = ", ".join(vocabulary)
        return (
            f"Rewrite exactly this German sentence for level {level}. "
            f"Preserve its meaning and replace only this uncertain wording with "
            f"common everyday words: {words}. Prefer the smallest possible change. "
            f"Return only one short German sentence.\nSentence: {sentence}"
        )

    issues = [
        item.get("metric") or item.get("feature")
        for item in decision["language"]["violations"]
        + decision["language"]["warnings"]
    ]
    issue_text = ", ".join(issue for issue in issues if issue) or "sentence complexity"
    return (
        f"Rewrite exactly this German sentence for level {level}. Preserve its "
        f"meaning, but simplify this issue: {issue_text}. Use common everyday "
        f"words and one short, simple sentence. Return only the rewritten German "
        f"sentence.\nSentence: {sentence}"
    )


def _store_feedback(feedback_store, decision):
    items = decision["record_for_feedback"]
    feedback_store["uncertain_vocabulary"].extend(items["uncertain_vocabulary"])
    feedback_store["language_warnings"].extend(items["language_warnings"])


def _validated_fallback(level, session_terms, decision_fn, diagnostics=None):
    if diagnostics is not None:
        diagnostics["fallback_used"] = True
    fallback = _decide_timed(
        decision_fn,
        FALLBACK_SENTENCE,
        level,
        diagnostics,
        session_terms=session_terms,
    )
    if fallback["action"] not in {DISPLAY, DISPLAY_AND_RECORD}:
        raise RuntimeError("The controlled fallback did not pass validation")
    return fallback


def validate_sentence_with_retries(
    sentence: str,
    level: str,
    rewrite_sentence: Callable[[str, str, int], Iterable[str]],
    *,
    session_terms=None,
    decision_fn=decide_response,
    diagnostics=None,
):
    """Return accepted text and its decision after at most two rewrites."""
    candidates = []
    candidate_text = sentence
    if diagnostics is not None:
        diagnostics.setdefault("generated_candidates", []).append(sentence)

    for attempt in range(MAX_REGENERATION_ATTEMPTS + 1):
        decision = _decide_timed(
            decision_fn,
            candidate_text,
            level,
            diagnostics,
            attempt=attempt,
            previous_candidates=candidates,
            session_terms=session_terms,
        )
        if decision["action"] in {DISPLAY, DISPLAY_AND_RECORD}:
            return decision["text"], decision
        if decision["action"] == FALLBACK:
            fallback = _validated_fallback(
                level, session_terms, decision_fn, diagnostics
            )
            return fallback["text"], fallback

        candidates.append(decision)
        if attempt < MAX_REGENERATION_ATTEMPTS:
            if diagnostics is not None:
                diagnostics["rewrites"] += 1
            instruction = _rewrite_instruction(candidate_text, level, decision)
            candidate_text = "".join(
                rewrite_sentence(candidate_text, instruction, attempt + 1)
            ).strip()
            if not candidate_text:
                candidate_text = FALLBACK_SENTENCE
            if diagnostics is not None:
                diagnostics.setdefault("rewritten_candidates", []).append(candidate_text)

    raise RuntimeError("Response validation ended without an accepted result")


def validated_response_stream(
    initial_chunks: Iterable[str],
    level: str,
    rewrite_sentence: Callable[[str, str, int], Iterable[str]],
    feedback_store: dict[str, list],
    *,
    session_terms=None,
    decision_fn=decide_response,
    diagnostics=None,
):
    """Yield only accepted sentences and collect feedback items server-side."""
    displayed = 0
    for sentence in iter_sentences(initial_chunks):
        if displayed >= MAX_RESPONSE_SENTENCES:
            break
        accepted_text, decision = validate_sentence_with_retries(
            sentence,
            level,
            rewrite_sentence,
            session_terms=session_terms,
            decision_fn=decision_fn,
            diagnostics=diagnostics,
        )
        _store_feedback(feedback_store, decision)
        yield (" " if displayed else "") + accepted_text.strip()
        displayed += 1

    if displayed == 0:
        fallback = _validated_fallback(
            level, session_terms, decision_fn, diagnostics
        )
        _store_feedback(feedback_store, fallback)
        yield fallback["text"]


def commit_accepted_exchange(history, user_message: str, assistant_reply: str) -> bool:
    """Add an exchange only after an accepted assistant reply exists."""
    if not assistant_reply or not assistant_reply.strip():
        return False
    history.extend(
        [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_reply.strip()},
        ]
    )
    return True
