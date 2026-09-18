"""Evaluate the frozen validator against the independent 150-case corpus."""

from collections import Counter, defaultdict

from tests.test_validator_generalization import load_generalization_cases
from validator import PASS, UNKNOWN, UNVERIFIED, validate_vocabulary


def main():
    cases = load_generalization_cases()
    expected_counts = Counter(case["expected"] for case in cases)
    actual_counts = Counter()
    matrix = Counter()
    mismatches = []
    unknown_tokens = Counter()
    category_mismatches = Counter()

    for case in cases:
        result = validate_vocabulary(
            case["sentence"], case["level"], session_terms=case.get("session_terms")
        )
        expected = case["expected"]
        actual = result["status"]
        actual_counts[actual] += 1
        matrix[(expected, actual)] += 1

        for token in result["tokens"]:
            if token["classification"] == UNVERIFIED:
                unknown_tokens[token["token"].casefold()] += 1

        if expected != actual:
            mismatches.append((case, result))
            category_mismatches[case["category"]] += 1

    false_passes = [item for item in mismatches if item[0]["expected"] != PASS and item[1]["status"] == PASS]
    false_fails = [item for item in mismatches if item[0]["expected"] == PASS and item[1]["status"] == "FAIL"]
    unexpected_unknowns = [item for item in mismatches if item[0]["expected"] == PASS and item[1]["status"] == UNKNOWN]

    print(f"Cases: {len(cases)}")
    print(f"Exact: {len(cases) - len(mismatches)}/{len(cases)} ({(len(cases) - len(mismatches)) / len(cases):.1%})")
    print(f"Expected: {dict(expected_counts)}")
    print(f"Actual:   {dict(actual_counts)}")
    print("Matrix:")
    for (expected, actual), count in sorted(matrix.items()):
        print(f"  {expected:7} -> {actual:7}: {count}")
    print(f"False PASSes: {len(false_passes)}")
    print(f"False FAILs: {len(false_fails)}")
    print(f"Unexpected UNKNOWNs: {len(unexpected_unknowns)}")

    print("\nAll mismatches:")
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

    print("\nMismatch categories:")
    for category, count in category_mismatches.most_common():
        print(f"  {count:>2}  {category}")

    print("\nRecurring UNKNOWN tokens:")
    for token, count in unknown_tokens.most_common():
        if count > 1:
            print(f"  {count:>2}  {token}")


if __name__ == "__main__":
    main()
