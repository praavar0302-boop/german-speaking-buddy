"""Read objective evidence from the normal roleplay response stream."""

from __future__ import annotations

import json
from itertools import chain


HEADER_START = "[[PROGRESS "
HEADER_END = "]]"


def progress_instruction(scenario):
    """Ask for objective evidence alongside the normal roleplay reply."""
    objectives = "\n".join(
        f"- {objective['id']}: {objective['text']}"
        for objective in scenario["objectives"]
    )
    return (
        "\n\nPRIVATE OBJECTIVE CHECK (not part of your spoken reply):\n"
        "Before your German reply, write one line in this exact form:\n"
        '[[PROGRESS {"objective_id":"exact quote from the latest learner message"}]]\n'
        "Use {} if no objective was completed. You may include several IDs. "
        "Judge meaning, not exact keywords, using the conversation so far. "
        "Only report an objective when the learner has actually done it; "
        "never report an action merely because you mentioned it. "
        "Each evidence quote must appear verbatim in the latest learner message. "
        "For multi-step objectives, report the ID only when the final required "
        "learner action occurs. If this completes every objective, give a brief "
        "in-character closing reply after this line, with no new question or task. "
        "Do not explain or repeat this private line.\n"
        "Objective IDs:\n"
        + objectives
    )


def split_progress_header(chunks):
    """Remove the private header before any text reaches sentence validation."""
    source = iter(chunks)
    buffer = ""

    for chunk in source:
        buffer += chunk
        stripped = buffer.lstrip()
        if not stripped.startswith(HEADER_START):
            if HEADER_START.startswith(stripped) and len(stripped) < len(HEADER_START):
                continue
            return {}, chain((buffer,), source)

        if HEADER_END in stripped:
            header, remainder = stripped.split(HEADER_END, 1)
            raw_json = header[len(HEADER_START) :]
            try:
                evidence = json.loads(raw_json)
            except json.JSONDecodeError:
                evidence = {}
            if not isinstance(evidence, dict):
                evidence = {}
            remainder = remainder.lstrip()
            return evidence, chain((remainder,), source) if remainder else source

        if len(buffer) > 4096:
            raise ValueError("Roleplay progress header is too long")

    if buffer.lstrip().startswith("[[PROGRESS"):
        return {}, iter(())
    return {}, iter((buffer,)) if buffer else iter(())


def update_progress(scenario, previous, evidence, learner_message):
    """Keep completed objectives and accept only evidence from the learner."""
    learner_text = " ".join(learner_message.casefold().split())
    updated = list(previous)
    for index, objective in enumerate(scenario["objectives"]):
        if updated[index]:
            continue
        quote = evidence.get(objective["id"])
        if not isinstance(quote, str):
            continue
        normalized_quote = " ".join(quote.casefold().split())
        if normalized_quote and normalized_quote in learner_text:
            updated[index] = True
    return updated
