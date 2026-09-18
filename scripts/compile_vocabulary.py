"""Compile raw Goethe vocabulary entries into traceable JSON records.

This performs conservative, source-aware structural cleanup only. It does not
lemmatize words, generate inflections, or guess linguistic forms.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOCABULARY_DIR = PROJECT_ROOT / "data" / "vocabulary"

ARTICLES = ("der ", "die ", "das ", "ein ", "eine ")
PLURAL_MARKER = re.compile(r"\s*\((?:pl\.|Pl\.)\)\s*$")
REFLEXIVE_PREFIX = re.compile(r"^\(sich\)\s+(.+)$")
REFLEXIVE_SUFFIX = re.compile(r"^(.+?)\s+\(sich\)$")
ABBREVIATION = re.compile(
    r"^(?:[A-ZÄÖÜ]{2,}|(?:[A-Za-zÄÖÜäöüß]\.)+(?:\s*[A-Za-zÄÖÜäöüß]\.)*|usw\.)$"
)
INFLECTION_NOTE = re.compile(r"^(?:[-=¨].*|[a-zäöüß]{1,3})$")
JOINED_ARTICLE = re.compile(r"[a-zäöüß-](?:der|die|das)\s+[A-ZÄÖÜ]")

# Each join below was checked against the official Goethe A1 PDF. The raw
# extraction remains unchanged; only compiled records are split. There is no
# general correction rule because it could silently alter legitimate entries.
A1_VERIFIED_SPLITS = {
    "diesdir": ("dies-", "dir"),
    "letztdie Leute (pl.)": ("letzt-", "die Leute (pl.)"),
    "lieblieben": ("lieb-", "lieben"),
    "Lieblingsdas Lied, -er": ("Lieblings-", "das Lied, -er"),
    "meistder Mensch, -en": ("meist-", "der Mensch, -en"),
    "nächstder Name, -n": ("nächst-", "der Name, -n"),
    "unserunten": ("unser-", "unten"),
    "welchdie Welt": ("welch-", "die Welt"),
}

A1_SOURCE_URL = "https://www.goethe.de/pro/relaunch/prf/de/A1_SD1_Wortliste_02.pdf"
A2_SOURCE_URL = (
    "https://www.goethe.de/pro/relaunch/prf/de/Goethe-Zertifikat_A2_Wortliste.pdf"
)

# Example-sentence text was attached to these A2 headword rows during PDF
# extraction. The replacement strings match the official headword column.
A2_VERIFIED_REPLACEMENTS = {
    "die Ermäßigung,-enFür": "die Ermäßigung,-en",
    "der Fotoapparat, -eIch": "der Fotoapparat, -e",
    "die Mannschaft,-enMeine": "die Mannschaft,-en",
    "der Supermarkt, ¨-eIch": "der Supermarkt, ¨-e",
    "der Wettbewerb, -eMein": "der Wettbewerb, -e",
}


def split_grouped_entry(entry: str) -> list[str]:
    """Split only explicit, spaced source alternatives."""
    return [part.strip() for part in re.split(r"\s+/\s+|;\s+", entry) if part.strip()]


def is_abbreviation(text: str) -> bool:
    return bool(ABBREVIATION.fullmatch(text)) or text in {"ca.", "d. h.", "z. B."}


def remove_article(text: str) -> tuple[str, str | None]:
    for article in ARTICLES:
        if text.startswith(article):
            return text[len(article) :], article.strip()
    return text, None


def compile_segment(
    segment: str,
    *,
    source_entry: str,
    source_line: int,
    level: str,
    segment_number: int,
    correction: dict[str, object] | None,
) -> dict[str, object]:
    fields = [field.strip() for field in segment.split(",")]
    head = fields[0]
    trailing = fields[1:]
    forms: list[str] = []
    inflection_notes: list[str] = []
    phrases: list[str] = []
    abbreviations: list[str] = []
    review: list[str] = []
    is_reflexive = False

    plural_match = PLURAL_MARKER.search(head)
    if plural_match:
        inflection_notes.append(plural_match.group(0).strip())
        head = PLURAL_MARKER.sub("", head).strip()

    if is_abbreviation(head) and not trailing:
        abbreviations.append(head)
        lemma: str | None = None
    else:
        reflexive = REFLEXIVE_PREFIX.fullmatch(head) or REFLEXIVE_SUFFIX.fullmatch(head)
        if reflexive:
            is_reflexive = True
            lemma = reflexive.group(1).strip()
            forms.append(f"sich {lemma}")
        elif head.startswith("sich ") and len(head.split()) == 2:
            lemma = head.removeprefix("sich ")
            forms.append(head)
        else:
            without_article, article = remove_article(head)
            if article:
                inflection_notes.append(f"article: {article}")
            if " " in without_article:
                lemma = None
                phrases.append(head)
            else:
                lemma = without_article

    for value in trailing:
        if not value:
            review.append("empty comma-separated field")
        elif INFLECTION_NOTE.fullmatch(value) or value.lower() in {"pl.", "sg."}:
            inflection_notes.append(value)
        elif value[0].isupper():
            review.append(f"possible additional headword in comma group: {value}")
        else:
            forms.append(value)

    if lemma and lemma.endswith("-"):
        review.append("productive stem, not a complete lemma")
    if "/" in head:
        review.append("unseparated slash alternatives within headword")
    if ("(" in head or ")" in head) and not is_reflexive:
        review.append("parenthetical content needs manual interpretation")
    if JOINED_ARTICLE.search(segment) and source_entry not in A1_VERIFIED_SPLITS:
        review.append("possible joined extraction artifact")
    if not lemma and not phrases and not abbreviations:
        review.append("no canonical lemma, phrase, or abbreviation identified")

    return {
        "lemma": lemma,
        "forms": forms,
        "phrases": phrases,
        "abbreviations": abbreviations,
        "inflection_notes": inflection_notes,
        "source_entry": source_entry,
        "source_line": source_line,
        "source_segment": segment,
        "source_segment_number": segment_number,
        "level": level,
        "manual_review": review,
        "correction": correction,
    }


def compile_level(level: str) -> dict[str, object]:
    source_path = VOCABULARY_DIR / f"{level.lower()}.txt"
    source_entries = source_path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, object]] = []

    for line_number, source_entry in enumerate(source_entries, start=1):
        verified_parts = A1_VERIFIED_SPLITS.get(source_entry) if level == "A1" else None
        if verified_parts:
            segments = list(verified_parts)
            correction: dict[str, object] | None = {
                "type": "verified_extraction_split",
                "original": source_entry,
                "replacement_entries": list(verified_parts),
                "verified_against": A1_SOURCE_URL,
            }
        elif level == "A2" and source_entry in A2_VERIFIED_REPLACEMENTS:
            replacement = A2_VERIFIED_REPLACEMENTS[source_entry]
            segments = [replacement]
            correction = {
                "type": "verified_example_text_removal",
                "original": source_entry,
                "replacement_entries": [replacement],
                "verified_against": A2_SOURCE_URL,
            }
        else:
            segments = split_grouped_entry(source_entry) or [source_entry]
            correction = None

        for segment_number, segment in enumerate(segments, start=1):
            records.append(
                compile_segment(
                    segment,
                    source_entry=source_entry,
                    source_line=line_number,
                    level=level,
                    segment_number=segment_number,
                    correction=correction,
                )
            )

    lemmas = {record["lemma"] for record in records if record["lemma"]}
    forms = {form for record in records for form in record["forms"]}
    phrases = {phrase for record in records for phrase in record["phrases"]}
    abbreviations = {
        abbreviation for record in records for abbreviation in record["abbreviations"]
    }

    return {
        "metadata": {
            "level": level,
            "scope": "level-specific" if level == "A1" else "cumulative through A2",
            "source_file": source_path.relative_to(PROJECT_ROOT).as_posix(),
            "source_entry_count": len(source_entries),
            "compiled_record_count": len(records),
            "unique_lemma_count": len(lemmas),
            "unique_form_count": len(forms),
            "unique_phrase_count": len(phrases),
            "unique_abbreviation_count": len(abbreviations),
            "manual_review_record_count": sum(
                bool(record["manual_review"]) for record in records
            ),
            "verified_correction_count": sum(
                source in A1_VERIFIED_SPLITS for source in source_entries
            )
            + sum(source in A2_VERIFIED_REPLACEMENTS for source in source_entries),
            "notes": [
                "Raw source entries are preserved in source_entry and source_line.",
                "No general lemmatization or generated inflection is performed.",
                "Counts are structural compiler counts, not claims about CEFR vocabulary size.",
            ],
        },
        "entries": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated files are current without changing them",
    )
    args = parser.parse_args()

    for level in ("A1", "A2"):
        compiled = compile_level(level)
        output_path = VOCABULARY_DIR / f"{level.lower()}.compiled.json"
        rendered = json.dumps(compiled, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not output_path.exists() or output_path.read_text(encoding="utf-8") != rendered:
                raise SystemExit(f"Out of date: {output_path.relative_to(PROJECT_ROOT)}")
        else:
            output_path.write_text(rendered, encoding="utf-8")

        metadata = compiled["metadata"]
        print(
            f"{level}: {metadata['source_entry_count']} source entries -> "
            f"{metadata['compiled_record_count']} records; "
            f"{metadata['unique_lemma_count']} lemmas, "
            f"{metadata['unique_form_count']} forms, "
            f"{metadata['unique_phrase_count']} phrases, "
            f"{metadata['unique_abbreviation_count']} abbreviations, "
            f"{metadata['manual_review_record_count']} review records"
        )


if __name__ == "__main__":
    main()
