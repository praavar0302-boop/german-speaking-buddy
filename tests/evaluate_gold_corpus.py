"""Print expected-versus-actual metrics for the vocabulary gold corpus."""

from collections import Counter

from tests.test_validator_gold import load_gold_cases
from validator import FAIL, PASS, UNKNOWN, UNVERIFIED, validate_vocabulary


def main():
    cases = load_gold_cases()
    expected_counts = Counter(case["expected"] for case in cases)
    actual_counts = Counter()
    mismatches = []
    unknown_words = Counter()

    for case in cases:
        result = validate_vocabulary(
            case["sentence"], case["level"], session_terms=case.get("session_terms")
        )
        actual_counts[result["status"]] += 1
        for token in result["tokens"]:
            if token["classification"] == UNVERIFIED:
                unknown_words[token["token"].casefold()] += 1
        if result["status"] != case["expected"]:
            mismatches.append((case, result))

    print(f"Cases: {len(cases)}")
    print(f"Expected: {dict(expected_counts)}")
    print(f"Actual:   {dict(actual_counts)}")
    print(f"Matches: {len(cases) - len(mismatches)}; mismatches: {len(mismatches)}")
    print("\nMismatches:")
    for case, result in mismatches:
        issues = ", ".join(
            f"{token['token']}={token['classification']}/{token['reason']}"
            for token in result["tokens"]
            if token["classification"] == UNVERIFIED
        )
        print(
            f"{case['id']} [{case['category']}] expected {case['expected']}, "
            f"actual {result['status']}: {issues or 'all tokens passed'}"
        )

    print("\nRecurring UNKNOWN tokens:")
    for word, count in unknown_words.most_common():
        print(f"{count:>2}  {word}")

    false_fails = [item for item in mismatches if item[0]["expected"] == PASS and item[1]["status"] == FAIL]
    false_passes = [item for item in mismatches if item[0]["expected"] != PASS and item[1]["status"] == PASS]
    print(f"\nFalse FAILs: {len(false_fails)}")
    print(f"False PASSes: {len(false_passes)}")


if __name__ == "__main__":
    main()
