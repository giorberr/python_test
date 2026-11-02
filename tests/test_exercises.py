"""Independent fixture oracles and integration tests for the full curriculum."""

import ast
import copy
import inspect
import textwrap
import unittest
from collections import Counter, deque
from itertools import combinations
from math import prod

from practice.checker import check
from practice.exercises import EXERCISES


def reference_contains_duplicate(nums):
    return any(nums[i] == nums[j] for i, j in combinations(range(len(nums)), 2))


def reference_two_sum(nums, target):
    seen = {}
    for index, value in enumerate(nums):
        if target - value in seen:
            return [seen[target - value], index]
        seen[value] = index
    return None


def reference_is_valid_parentheses(text):
    previous = None
    while text != previous:
        previous = text
        for pair in ("()", "[]", "{}"):
            text = text.replace(pair, "")
    return text == ""


def reference_max_profit(prices):
    return max(
        [0] + [prices[j] - prices[i] for i, j in combinations(range(len(prices)), 2)]
    )


def reference_binary_search(nums, target):
    left, right = 0, len(nums) - 1
    while left <= right:
        middle = (left + right) // 2
        if nums[middle] == target:
            return middle
        if nums[middle] < target:
            left = middle + 1
        else:
            right = middle - 1
    return -1


def reference_max_depth(tree):
    if not tree:
        return 0
    root = [tree[0], None, None]
    pending, index = deque([root]), 1
    while pending and index < len(tree):
        parent = pending.popleft()
        for slot in (1, 2):
            if index == len(tree):
                break
            value = tree[index]
            index += 1
            if value is not None:
                child = [value, None, None]
                parent[slot] = child
                pending.append(child)

    def depth(node):
        if node is None:
            return 0
        return 1 + max(depth(node[1]), depth(node[2]))

    return depth(root)


def reference_group_anagrams(words):
    groups = {}
    for word in words:
        signature = tuple(sorted(Counter(word).items()))
        groups.setdefault(signature, []).append(word)
    return list(groups.values())


def reference_length_of_longest_substring(text):
    return max(
        [0]
        + [
            end - start
            for start in range(len(text))
            for end in range(start + 1, len(text) + 1)
            if len(set(text[start:end])) == end - start
        ]
    )


def reference_three_sum(nums):
    nums = sorted(nums)
    triples = []
    for index in range(len(nums) - 2):
        if index and nums[index] == nums[index - 1]:
            continue
        left, right = index + 1, len(nums) - 1
        while left < right:
            total = nums[index] + nums[left] + nums[right]
            if total < 0:
                left += 1
            elif total > 0:
                right -= 1
            else:
                triples.append([nums[index], nums[left], nums[right]])
                left += 1
                right -= 1
                while left < right and nums[left] == nums[left - 1]:
                    left += 1
                while left < right and nums[right] == nums[right + 1]:
                    right -= 1
    return triples


def reference_merge_intervals(intervals):
    intervals.sort(key=lambda interval: interval[0])
    merged = []
    for interval in intervals:
        if merged and interval[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], interval[1])
        else:
            merged.append(interval)
    return merged


def reference_product_except_self(nums):
    return [prod(nums[:index] + nums[index + 1 :]) for index in range(len(nums))]


def reference_subarray_sum(nums, k):
    return sum(
        sum(nums[start:end]) == k
        for start in range(len(nums))
        for end in range(start + 1, len(nums) + 1)
    )


def reference_top_k_frequent(nums, k):
    return [value for value, count in Counter(nums).most_common(k)]


def reference_num_islands(grid):
    land = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == "1"
    }
    islands = 0
    while land:
        islands += 1
        pending = [land.pop()]
        while pending:
            row, column = pending.pop()
            for neighbor in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if neighbor in land:
                    land.remove(neighbor)
                    pending.append(neighbor)
    return islands


def reference_coin_change(coins, amount):
    pending, visited = deque([(0, 0)]), {0}
    while pending:
        value, count = pending.popleft()
        if value == amount:
            return count
        for denomination in set(coins):
            next_value = value + denomination
            if next_value <= amount and next_value not in visited:
                visited.add(next_value)
                pending.append((next_value, count + 1))
    return -1


REFERENCES = {
    "contains-duplicate": reference_contains_duplicate,
    "two-sum": reference_two_sum,
    "valid-parentheses": reference_is_valid_parentheses,
    "best-time-to-buy-and-sell-stock": reference_max_profit,
    "binary-search": reference_binary_search,
    "maximum-depth-of-binary-tree": reference_max_depth,
    "group-anagrams": reference_group_anagrams,
    "longest-substring-without-repeating-characters": reference_length_of_longest_substring,
    "3sum": reference_three_sum,
    "merge-intervals": reference_merge_intervals,
    "product-of-array-except-self": reference_product_except_self,
    "subarray-sum-equals-k": reference_subarray_sum,
    "top-k-frequent-elements": reference_top_k_frequent,
    "number-of-islands": reference_num_islands,
    "coin-change": reference_coin_change,
}

VALIDATORS = {
    "two-sum": "two_sum",
    "binary-search": "binary_search",
    "group-anagrams": "group_anagrams",
    "3sum": "three_sum",
    "merge-intervals": "merge_intervals",
    "top-k-frequent-elements": "top_k_frequent",
}


def interval_components(intervals):
    """Merge via overlap-graph components, independently of the sorting solution."""
    unseen, merged = set(range(len(intervals))), []
    while unseen:
        component = {unseen.pop()}
        pending = list(component)
        while pending:
            index = pending.pop()
            for other in list(unseen):
                if (
                    intervals[index][0] <= intervals[other][1]
                    and intervals[other][0] <= intervals[index][1]
                ):
                    unseen.remove(other)
                    component.add(other)
                    pending.append(other)
        merged.append(
            (
                min(intervals[index][0] for index in component),
                max(intervals[index][1] for index in component),
            )
        )
    return sorted(merged)


def submission_source(exercise, implementation, transform=None):
    # Send self-contained source, not test-module callables, to Windows spawn.
    source = (
        "from collections import Counter, deque\n"
        "from itertools import combinations\n"
        "from math import prod\n\n"
    )
    source += textwrap.dedent(inspect.getsource(implementation))
    function = ast.parse(exercise["starter"]).body[0]
    if transform is None:
        return source + "\n" + function.name + " = " + implementation.__name__ + "\n"
    arguments = ", ".join(argument.arg for argument in function.args.args)
    return source + (
        f"\ndef {function.name}({arguments}):\n"
        f"    result = {implementation.__name__}({arguments})\n"
        f"    return {transform}\n"
    )


def incorrect_endpoint_duplicates(nums):
    return len(nums) > 1 and nums[0] == nums[-1]


def incorrect_substring_without_final_update(text):
    seen, left, best = set(), 0, 0
    for right, character in enumerate(text):
        if character in seen:
            best = max(best, right - left)
            while character in seen:
                seen.remove(text[left])
                left += 1
        seen.add(character)
    return best


def incorrect_merge_using_previous_end(intervals):
    merged, previous_end = [], None
    for start, end in sorted(intervals):
        if previous_end is not None and start <= previous_end:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
        previous_end = end
    return merged


def incorrect_down_right_islands(grid):
    if not grid or not grid[0]:
        return 0
    rows, columns, islands = len(grid), len(grid[0]), 0

    def visit(row, column):
        if row >= rows or column >= columns or grid[row][column] != "1":
            return
        grid[row][column] = "0"
        visit(row + 1, column)
        visit(row, column + 1)

    for row in range(rows):
        for column in range(columns):
            if grid[row][column] == "1":
                islands += 1
                visit(row, column)
    return islands


def incorrect_coin_change_assuming_sorted(coins, amount):
    best = [0] + [amount + 1] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin > value:
                break
            best[value] = min(best[value], best[value - coin] + 1)
    return best[amount] if best[amount] <= amount else -1


def incorrect_subarray_ignoring_negative_k(nums, k):
    if k < 0:
        return 0
    return sum(
        sum(nums[start:end]) == k
        for start in range(len(nums))
        for end in range(start + 1, len(nums) + 1)
    )


def incorrect_heap_indexed_depth(tree):
    def depth(index):
        if index >= len(tree) or tree[index] is None:
            return 0
        return 1 + max(depth(2 * index + 1), depth(2 * index + 2))

    return depth(0)


REGRESSIONS = [
    ("contains-duplicate", incorrect_endpoint_duplicates, ([1, 2, 2, 3],)),
    (
        "longest-substring-without-repeating-characters",
        incorrect_substring_without_final_update,
        ("abcd",),
    ),
    (
        "merge-intervals",
        incorrect_merge_using_previous_end,
        ([[1, 10], [2, 3], [4, 5]],),
    ),
    (
        "number-of-islands",
        incorrect_down_right_islands,
        ([["1", "0", "1"], ["1", "1", "1"]],),
    ),
    ("coin-change", incorrect_coin_change_assuming_sorted, ([5, 1, 2], 3)),
    (
        "subarray-sum-equals-k",
        incorrect_subarray_ignoring_negative_k,
        ([-1, -1, 1], -1),
    ),
    (
        "maximum-depth-of-binary-tree",
        incorrect_heap_indexed_depth,
        ([1, None, 2, None, 3, None, 4],),
    ),
]


class ExerciseTests(unittest.TestCase):
    def test_curriculum_contract(self):
        self.assertEqual([exercise["id"] for exercise in EXERCISES], list(REFERENCES))
        for exercise in EXERCISES:
            with self.subTest(exercise=exercise["id"]):
                function = ast.parse(exercise["starter"]).body[0]
                reference = REFERENCES[exercise["id"]]
                self.assertEqual(function.name, reference.__name__[len("reference_") :])
                self.assertEqual(
                    exercise.get("validator"), VALIDATORS.get(exercise["id"])
                )
                self.assertTrue(exercise["description"])
                self.assertTrue(exercise["cases"])

    def test_case_arguments_match_starters(self):
        for exercise in EXERCISES:
            function = ast.parse(exercise["starter"]).body[0]
            seen = set()
            for number, case in enumerate(exercise["cases"], 1):
                with self.subTest(exercise=exercise["id"], case=number):
                    self.assertIs(type(case["args"]), tuple)
                    self.assertEqual(len(case["args"]), len(function.args.args))
                    self.assertIn("expected", case)
                    self.assertNotIn(repr(case["args"]), seen)
                    seen.add(repr(case["args"]))

    def test_merge_inputs_are_mutable_lists(self):
        exercise = next(item for item in EXERCISES if item["id"] == "merge-intervals")
        for case in exercise["cases"]:
            (intervals,) = case["args"]
            self.assertIs(type(intervals), list)
            for interval in intervals:
                self.assertIs(type(interval), list)
                self.assertEqual(len(interval), 2)
                self.assertTrue(all(type(value) is int for value in interval))
                self.assertLessEqual(interval[0], interval[1])

    def assert_exact(self, actual, expected):
        self.assertIs(type(actual), type(expected))
        if isinstance(actual, (list, tuple)):
            self.assertEqual(len(actual), len(expected))
            for value, reference in zip(actual, expected):
                self.assert_exact(value, reference)
        else:
            self.assertEqual(actual, expected)

    def assert_integer_sequence(self, values, length=None):
        self.assertIsInstance(values, (list, tuple))
        if length is not None:
            self.assertEqual(len(values), length)
        self.assertTrue(all(type(value) is int for value in values))

    def assert_valid_expected(self, exercise, case):
        args, expected = case["args"], case["expected"]
        exercise_id = exercise["id"]
        if exercise_id == "two-sum":
            nums, target = args
            pairs = {
                (i, j)
                for i, j in combinations(range(len(nums)), 2)
                if nums[i] + nums[j] == target
            }
            if not pairs:
                self.assertIsNone(expected)
            else:
                self.assert_integer_sequence(expected, 2)
                self.assertIn(tuple(sorted(expected)), pairs)
        elif exercise_id == "binary-search":
            nums, target = args
            self.assertIs(type(expected), int)
            if target in nums:
                self.assertTrue(0 <= expected < len(nums))
                self.assertEqual(nums[expected], target)
            else:
                self.assertEqual(expected, -1)
        elif exercise_id == "group-anagrams":
            groups = {}
            for word in args[0]:
                groups.setdefault("".join(sorted(word)), []).append(word)
            self.assertIsInstance(expected, (list, tuple))
            for group in expected:
                self.assertIsInstance(group, (list, tuple))
                self.assertTrue(all(type(word) is str for word in group))
            self.assertEqual(
                sorted(tuple(sorted(group)) for group in expected),
                sorted(tuple(sorted(group)) for group in groups.values()),
            )
        elif exercise_id == "3sum":
            triples = {
                tuple(sorted(triple))
                for triple in combinations(args[0], 3)
                if sum(triple) == 0
            }
            self.assertIsInstance(expected, (list, tuple))
            for triple in expected:
                self.assert_integer_sequence(triple, 3)
            self.assertEqual(
                sorted(tuple(sorted(triple)) for triple in expected), sorted(triples)
            )
        elif exercise_id == "merge-intervals":
            self.assertIsInstance(expected, (list, tuple))
            for interval in expected:
                self.assert_integer_sequence(interval, 2)
            self.assertEqual(
                sorted(tuple(interval) for interval in expected),
                interval_components(args[0]),
            )
        elif exercise_id == "top-k-frequent-elements":
            nums, k = args
            counts = {value: nums.count(value) for value in set(nums)}
            self.assert_integer_sequence(expected, k)
            self.assertEqual(len(set(expected)), k)
            self.assertTrue(set(expected) <= counts.keys())
            if expected:
                minimum_selected = min(counts[value] for value in expected)
                self.assertTrue(
                    all(
                        count <= minimum_selected
                        for value, count in counts.items()
                        if value not in expected
                    )
                )
        else:
            reference = REFERENCES[exercise_id](*copy.deepcopy(args))
            self.assert_exact(expected, reference)

    def test_expected_values_match_independent_references(self):
        for exercise in EXERCISES:
            for number, case in enumerate(exercise["cases"], 1):
                with self.subTest(exercise=exercise["id"], case=number):
                    self.assert_valid_expected(exercise, case)

    def run_submission(self, exercise, implementation, transform=None):
        result = check(
            submission_source(exercise, implementation, transform), exercise, timeout=10
        )
        self.assertNotIn("error", result, repr(result))
        self.assertEqual(len(result["results"]), len(exercise["cases"]))
        return result["results"]

    def test_reference_solutions_pass_actual_checker(self):
        snapshot = copy.deepcopy(EXERCISES)
        for exercise in EXERCISES:
            with self.subTest(exercise=exercise["id"]):
                results = self.run_submission(exercise, REFERENCES[exercise["id"]])
                failures = [result for result in results if not result["passed"]]
                self.assertEqual(failures, [])
        self.assertEqual(EXERCISES, snapshot)

    def test_equivalent_outputs_pass_actual_checker(self):
        transforms = {
            "two-sum": "None if result is None else tuple(reversed(result))",
            "binary-search": "max((i for i, value in enumerate(nums) "
            "if value == target), default=-1)",
            "group-anagrams": "[list(reversed(group)) for group in reversed(result)]",
            "3sum": "tuple(tuple(reversed(triple)) for triple in reversed(result))",
            "merge-intervals": "tuple(tuple(interval) for interval in reversed(result))",
            "top-k-frequent-elements": "tuple(reversed(result))",
        }
        for exercise in EXERCISES:
            if exercise["id"] in transforms:
                with self.subTest(exercise=exercise["id"]):
                    results = self.run_submission(
                        exercise, REFERENCES[exercise["id"]], transforms[exercise["id"]]
                    )
                    failures = [result for result in results if not result["passed"]]
                    self.assertEqual(failures, [])

    def test_known_incorrect_variants_are_rejected(self):
        exercises = {exercise["id"]: exercise for exercise in EXERCISES}
        for exercise_id, implementation, regression_args in REGRESSIONS:
            with self.subTest(exercise=exercise_id):
                exercise = exercises[exercise_id]
                results = self.run_submission(exercise, implementation)
                regression_results = [
                    result
                    for case, result in zip(exercise["cases"], results)
                    if case["args"] == regression_args
                ]
                self.assertTrue(regression_results, "Missing regression case")
                self.assertTrue(
                    all(not result["passed"] for result in regression_results),
                    repr(regression_results),
                )


if __name__ == "__main__":
    unittest.main()
