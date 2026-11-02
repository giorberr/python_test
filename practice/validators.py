"""Type-aware answer checks for the trusted, local practice runner."""

from collections import Counter


def _sequence(value):
    # Only inspect built-in containers, not arbitrary iterators or overloaded types.
    return type(value) in (list, tuple)


def _equal(actual, expected, depth=0):
    """Compare built-in values without bool/int coercion or custom equality."""
    if depth > 40:
        return False
    actual_type, expected_type = type(actual), type(expected)
    if _sequence(expected):
        return (
            _sequence(actual)
            and len(actual) == len(expected)
            and all(_equal(a, e, depth + 1) for a, e in zip(actual, expected))
        )
    if actual_type is not expected_type:
        return False
    if expected_type is dict:
        if len(actual) != len(expected):
            return False
        unmatched = list(actual.items())
        for key, value in expected.items():
            for index, (other_key, other_value) in enumerate(unmatched):
                if _equal(other_key, key, depth + 1) and _equal(
                    other_value, value, depth + 1
                ):
                    unmatched.pop(index)
                    break
            else:
                return False
        return True
    if expected_type in (set, frozenset):
        if len(actual) != len(expected):
            return False
        unmatched = list(actual)
        for value in expected:
            for index, other in enumerate(unmatched):
                if _equal(other, value, depth + 1):
                    unmatched.pop(index)
                    break
            else:
                return False
        return True
    if expected_type in (type(None), bool, int, float, complex, str, bytes):
        return (actual == expected) is True
    return False


def _default(actual, args, expected):
    return _equal(actual, expected)


def _two_sum(actual, args, expected):
    nums, target = args
    if actual is None:
        seen = set()
        for number in nums:
            if target - number in seen:
                return False
            seen.add(number)
        return True
    if (
        not _sequence(actual)
        or len(actual) != 2
        or any(type(index) is not int for index in actual)
    ):
        return False
    left, right = actual
    return (
        left != right
        and 0 <= left < len(nums)
        and 0 <= right < len(nums)
        and nums[left] + nums[right] == target
    )


def _group_anagrams(actual, args, expected):
    if not _sequence(actual):
        return False
    groups = {}
    for word in args[0]:
        groups.setdefault("".join(sorted(word)), []).append(word)
    if len(actual) != len(groups):
        return False
    if any(not _sequence(group) or not group for group in actual):
        return False
    if sum(map(len, actual)) != len(args[0]):
        return False
    if any(type(word) is not str for group in actual for word in group):
        return False
    return sorted(tuple(sorted(group)) for group in actual) == sorted(
        tuple(sorted(group)) for group in groups.values()
    )


def _three_sum(actual, args, expected):
    if not _sequence(actual):
        return False
    expected_triples = {tuple(sorted(triple)) for triple in expected}
    if len(actual) != len(expected_triples):
        return False
    available = Counter(args[0])
    triples = set()
    for triple in actual:
        if (
            not _sequence(triple)
            or len(triple) != 3
            or any(type(number) is not int for number in triple)
        ):
            return False
        canonical = tuple(sorted(triple))
        if canonical in triples or sum(canonical) != 0:
            return False
        if any(
            count > available[number] for number, count in Counter(canonical).items()
        ):
            return False
        triples.add(canonical)
    return triples == expected_triples


def _merge_intervals(actual, args, expected):
    if not _sequence(actual):
        return False
    expected_intervals = {tuple(interval) for interval in expected}
    if len(actual) != len(expected_intervals):
        return False
    intervals = set()
    for interval in actual:
        if (
            not _sequence(interval)
            or len(interval) != 2
            or any(type(endpoint) is not int for endpoint in interval)
        ):
            return False
        start, end = interval
        canonical = (start, end)
        if start > end or canonical in intervals:
            return False
        intervals.add(canonical)
    return intervals == expected_intervals


def _top_k_frequent(actual, args, expected):
    nums, k = args
    if (
        not _sequence(actual)
        or len(actual) != k
        or any(type(number) is not int for number in actual)
    ):
        return False
    selected = set(actual)
    frequencies = Counter(nums)
    if len(selected) != k or any(number not in frequencies for number in selected):
        return False
    if not selected:
        return True
    cutoff = max(
        (count for number, count in frequencies.items() if number not in selected),
        default=0,
    )
    return min(frequencies[number] for number in selected) >= cutoff


def _binary_search(actual, args, expected):
    if type(actual) is not int:
        return False
    nums, target = args
    if actual == -1:
        return target not in nums
    return 0 <= actual < len(nums) and nums[actual] == target


_VALIDATORS = {
    "two_sum": _two_sum,
    "group_anagrams": _group_anagrams,
    "three_sum": _three_sum,
    "merge_intervals": _merge_intervals,
    "top_k_frequent": _top_k_frequent,
    "binary_search": _binary_search,
}


def get_validator(name=None):
    """Return a boolean answer predicate accepting (actual, original_args, expected)."""
    if name is None:
        return _default
    if type(name) is not str or name not in _VALIDATORS:
        raise ValueError("Unknown exercise validator; check the exercise definition.")
    return _VALIDATORS[name]
