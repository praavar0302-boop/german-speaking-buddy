# German vocabulary data

GermanSpeakingBuddy uses vocabulary material from the official Goethe-Institut
A1 and A2 examination word lists. These are Goethe vocabulary lists for the
relevant levels, not exhaustive official CEFR vocabulary lists.

Accessed: 2026-09-16

## How the vocabulary is used

The original extracted entries are kept unchanged in `a1.txt` and `a2.txt`.
This preserves what came from the Goethe sources and makes every later cleanup
or correction traceable.

The project then cleans and organizes those entries into `a1.compiled.json` and
`a2.compiled.json`. These files separate useful information such as the main
word, source-supplied forms, phrases, and abbreviations while retaining the
original source entry.

The standalone vocabulary checker can now compare German text with the
vocabulary available for the selected learner level. A1 uses the A1 data; A2
uses the cumulative A2 data. Because a word list cannot prove the level of every
possible German word or inflected form, words without enough evidence are
reported as uncertain rather than automatically marked wrong.

Vocabulary checking is not yet connected to the live chatbot. Sentence-length
and structural checking have also been built as a separate standalone feature.
Grammar checking will be added later.

## Sources

### A1

- Goethe-Institut, *Goethe-Zertifikat A1: Start Deutsch 1 – Wortliste*
- [Official A1 PDF](https://www.goethe.de/pro/relaunch/prf/de/A1_SD1_Wortliste_02.pdf)
- Accessed PDF SHA-256:
  `45fb648bc0ac02338f7898cae065953e320ab72ed0c14e13e0deffe6f1c5d64e`
- Scope: A1 examination vocabulary material
- Extracted data: 797 unique source entries

The document describes approximately 650 main entries. The extracted file has
more rows because it also preserves secondary entries and word-group material.

### A2

- Goethe-Institut, *Goethe-Zertifikat A2 – Wortliste: Deutschprüfung für
  Jugendliche und Erwachsene*
- [Official A2 PDF](https://www.goethe.de/pro/relaunch/prf/de/Goethe-Zertifikat_A2_Wortliste.pdf)
- Accessed PDF SHA-256:
  `c9ca0c96c4adb252f253e1cc648b95ea031e417911565db07f7102bccdbdb19e`
- Scope: cumulative vocabulary material through A2
- Extracted data: 1,412 unique source entries

The Goethe A2 source does not identify which individual entries are new at A2.
For that reason, `a2.txt` preserves the complete cumulative list instead of
guessing an A2-only difference list.

## Traceability

The vocabulary was extracted from the PDFs' embedded text, with entries checked
against the source layout where necessary. Basic cleanup removed duplicate rows
and obvious formatting artifacts, but no missing vocabulary was invented and no
general lemmatization was applied.

Where extraction joined entries or example text together, corrections were made
only after checking the official PDFs. The unchanged original line is still
stored in the raw file and referenced by the compiled record. Entries that
cannot be interpreted confidently remain marked for review.

Run `python scripts/compile_vocabulary.py --check` to confirm that the compiled
files still match the preserved source data.
