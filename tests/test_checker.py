import multiprocessing
import time
import unittest
from typing import Any
from unittest import mock

from practice import checker
from practice.checker import check
from practice.validators import get_validator


def exercise(args=(), expected=None, validator=None, cases=None):
    definition = {
        "starter": "def solve(*args):\n    pass\n",
        "cases": cases if cases is not None else [{"args": args, "expected": expected}],
    }
    if validator is not None:
        definition["validator"] = validator
    return definition


class TruthyEquality:
    def __eq__(self, other) -> Any:
        return [True]


class AlwaysEqual:
    def __eq__(self, other):
        return True


class IntegerSubclass(int):
    pass


class ValidatorTests(unittest.TestCase):
    def assert_answers(self, name, args, expected, valid, invalid):
        validate = get_validator(name)
        for passed, answers in ((True, valid), (False, invalid)):
            for actual in answers:
                with self.subTest(validator=name, actual=repr(actual), passed=passed):
                    self.assertIs(validate(actual, args, expected), passed)

    def test_default_type_aware_comparison(self):
        validate = get_validator()
        valid = [
            (True, True),
            (0, 0),
            (None, None),
            ("a", "a"),
            ((1, (2, 3)), [1, [2, 3]]),
            ([], ()),
            ({"values": (1, 2)}, {"values": [1, 2]}),
            ({1, 2}, {2, 1}),
        ]
        invalid = [
            (False, 0),
            (True, 1),
            (0, False),
            (1, True),
            (1.0, 1),
            ([False], [0]),
            ((1,), [True]),
            ([1, 2], [2, 1]),
            ("1", 1),
            (None, 0),
            ({"flag": False}, {"flag": 0}),
            ({False: "x"}, {0: "x"}),
            ({False}, {0}),
            (TruthyEquality(), 1),
            (AlwaysEqual(), 1),
            (TruthyEquality(), TruthyEquality()),
            (IntegerSubclass(1), 1),
            (iter([1]), [1]),
        ]
        for actual, expected in valid:
            with self.subTest(actual=actual, expected=expected):
                self.assertIs(validate(actual, (), expected), True)
        for actual, expected in invalid:
            with self.subTest(actual=actual, expected=expected):
                self.assertIs(validate(actual, (), expected), False)
        cyclic = []
        cyclic.append(cyclic)
        self.assertIs(validate(cyclic, (), cyclic), False)

    def test_unknown_validator_is_an_explicit_configuration_error(self):
        for name in ("unknown", "", 1, [], {}):
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "Unknown.*validator"
            ):
                get_validator(name)

    def test_two_sum_equivalent_pairs_and_exact_indices(self):
        self.assert_answers(
            "two_sum",
            ([1, 2, 3, 4], 5),
            (0, 3),
            valid=[(3, 0), [1, 2], (2, 1), [0, 3]],
            invalid=[
                None,
                (0, 0),
                (-1, 0),
                (0, 4),
                (0, 1),
                [False, 3],
                [0.0, 3],
                [IntegerSubclass(0), 3],
                [],
                [0],
                [0, 3, 1],
                {0, 3},
                "03",
                3,
                {"i": 0, "j": 3},
                iter([0, 3]),
            ],
        )
        self.assert_answers(
            "two_sum",
            ([3, 3], 6),
            (0, 1),
            valid=[(1, 0)],
            invalid=[None, (0, 0), (1, 1)],
        )

    def test_two_sum_none_only_when_no_distinct_pair_exists(self):
        for args in (([], 0), ([3], 6), ([1, 2], 9)):
            self.assert_answers(
                "two_sum",
                args,
                None,
                valid=[None],
                invalid=[[], False, (-1, -1), (0, 0)],
            )
        # Existence is checked from the input, not inferred from expected's shape.
        self.assertIs(get_validator("two_sum")(None, ([2, 2], 4), None), False)

    def test_group_anagrams_order_duplicates_and_case(self):
        args = (["ab", "ba", "ab", "Ab", "", ""],)
        expected = [["", ""], ["Ab"], ["ab", "ab", "ba"]]
        self.assert_answers(
            "group_anagrams",
            args,
            expected,
            valid=[
                (("ba", "ab", "ab"), ("Ab",), ("", "")),
                [["Ab"], ["", ""], ["ab", "ba", "ab"]],
            ],
            invalid=[
                None,
                "ab",
                {"ab", "ba"},
                [["ab", "ba"], ["Ab"], ["", ""]],
                [["ab", "ba", "ab"], ["ab"], ["", ""]],
                [["ab", "ba", "ab", "Ab"], ["", ""]],
                [["ab", "ab"], ["ba"], ["Ab"], ["", ""]],
                [["ab", "ba", "ab"], ["ab"], ["", ""]],
                [["ab", "ba", "ab"], ["Ab"], ["", ""], []],
                [["ab", "ba", "ab"], ["Ab"], ["", 0]],
                ["ab", ["Ab"], ["", ""]],
                [set(["ab", "ba"]), ["Ab"], ["", ""]],
            ],
        )
        self.assert_answers(
            "group_anagrams", ([],), [], valid=[[], ()], invalid=[None, [[]], [()], {}]
        )

    def test_group_anagrams_cannot_split_a_single_signature(self):
        self.assert_answers(
            "group_anagrams",
            (["ab", "ba", "ab"],),
            [["ab", "ab", "ba"]],
            valid=[[["ba", "ab", "ab"]]],
            invalid=[[["ab"], ["ab", "ba"]], [["ab", "ba"]]],
        )
        self.assert_answers(
            "group_anagrams",
            (["aab", "abb"],),
            [["aab"], ["abb"]],
            valid=[(("abb",), ("aab",))],
            invalid=[[["aab", "abb"]]],
        )

    def test_three_sum_canonical_set_types_and_duplicates(self):
        args = ([-1, 0, 1, 2, -1, -4],)
        expected = [[-1, -1, 2], [-1, 0, 1]]
        self.assert_answers(
            "three_sum",
            args,
            expected,
            valid=[((1, -1, 0), [2, -1, -1]), [[-1, -1, 2], [0, 1, -1]]],
            invalid=[
                None,
                set(),
                [],
                [[-1, 0, 1]],
                [[-1, 0, 1], [1, -1, 0]],
                [[-1, -1, 2], [-1, False, 1]],
                [[-1, -1, 2], [-1.0, 0, 1]],
                [[-1, -1, 2], [-1, 0]],
                [[-1, -1, 2], [-1, 0, 1, 0]],
                [[-1, -1, 2], [-1, 0, 2]],
                [[-1, -1, 2], {-1, 0, 1}],
            ],
        )

    def test_three_sum_respects_input_multiplicity_and_empty_outputs(self):
        self.assert_answers(
            "three_sum",
            ([0, 0, 0, 0],),
            [(0, 0, 0)],
            valid=[[[0, 0, 0]]],
            invalid=[[[0, 0, 0], [0, 0, 0]], [[False, 0, 0]]],
        )
        self.assert_answers(
            "three_sum", ([0, 0],), [], valid=[[], ()], invalid=[None, [[0, 0, 0]]]
        )
        # Even bad expected metadata must not permit reuse of a missing input occurrence.
        self.assertIs(
            get_validator("three_sum")([(0, 0, 0)], ([0, 0],), [(0, 0, 0)]), False
        )
        self.assertIs(
            get_validator("three_sum")([(-2, 1, 1)], ([-2, 1],), [(-2, 1, 1)]), False
        )

    def test_merge_intervals_normalizes_expected_and_rejects_duplicates(self):
        args = ([(1, 3), (2, 6), (8, 10)],)
        expected = [[8, 10], [1, 6]]
        self.assert_answers(
            "merge_intervals",
            args,
            expected,
            valid=[[(1, 6), (8, 10)], ((8, 10), [1, 6])],
            invalid=[
                None,
                [],
                {(1, 6), (8, 10)},
                [(1, 6), (1, 6)],
                [(1, 6), (8, 10), (8, 10)],
                [(1, 3), (2, 6), (8, 10)],
                [(1, 10)],
                [(6, 1), (8, 10)],
                [(True, 6), (8, 10)],
                [(1.0, 6), (8, 10)],
                [(1, 6, 7), (8, 10)],
                [(1, 6), "8,10"],
            ],
        )
        self.assert_answers(
            "merge_intervals", ([],), [], valid=[[], ()], invalid=[None, [(0, 0)]]
        )
        self.assert_answers(
            "merge_intervals",
            ([(2, 2), (2, 2)],),
            [[2, 2]],
            valid=[((2, 2),)],
            invalid=[[(2, 2), (2, 2)]],
        )

    def test_top_k_arbitrary_cutoff_ties_not_arbitrary_frequencies(self):
        args = ([1, 1, 1, 2, 2, 3, 3, 4], 2)
        self.assert_answers(
            "top_k_frequent",
            args,
            [1, 2],
            valid=[[3, 1], (2, 1), [1, 3]],
            invalid=[
                None,
                [2, 3],
                [1, 4],
                [1, 1],
                [1, 9],
                [],
                [1],
                [1, 2, 3],
                [True, 2],
                [1.0, 2],
                {1, 2},
                iter([1, 2]),
            ],
        )
        self.assert_answers(
            "top_k_frequent",
            ([4, 4, -1, -1, 2, 2], 2),
            [-1, 2],
            valid=[[4, -1], (2, 4), [-1, 2]],
            invalid=[[4, 4]],
        )
        self.assert_answers(
            "top_k_frequent",
            ([1, 2, 3], 3),
            [1, 2, 3],
            valid=[(3, 2, 1)],
            invalid=[[1, 2, 4]],
        )
        for nums in ([], [1, 2]):
            self.assert_answers(
                "top_k_frequent",
                (nums, 0),
                [],
                valid=[[], ()],
                invalid=[None, [1], set()],
            )

    def test_binary_search_any_matching_index_but_exact_int(self):
        self.assert_answers(
            "binary_search",
            ([1, 2, 2, 2, 5], 2),
            1,
            valid=[1, 2, 3],
            invalid=[
                -1,
                -2,
                0,
                4,
                5,
                True,
                1.0,
                [1],
                None,
                IntegerSubclass(1),
                TruthyEquality(),
            ],
        )
        self.assert_answers(
            "binary_search", ([5], 5), 0, valid=[0], invalid=[False, -1]
        )
        for args in (([], 1), ([1, 3], 2)):
            self.assert_answers(
                "binary_search",
                args,
                -1,
                valid=[-1],
                invalid=[0, False, None, -1.0, "-1", -2],
            )


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.children_before = {
            process.pid for process in multiprocessing.active_children()
        }

    def tearDown(self):
        remaining = {process.pid for process in multiprocessing.active_children()}
        self.assertFalse(
            remaining - self.children_before, "Checker left a live child process"
        )

    def assert_passes(self, result, count=1):
        self.assertNotIn("error", result, result)
        self.assertEqual(len(result["results"]), count)
        for case in result["results"]:
            self.assertIs(case["passed"], True, case)
            for field in ("input", "expected", "actual"):
                self.assertIsInstance(case[field], str)

    def test_correct_solution_and_display_contract_without_output(self):
        definition = exercise(([1, 2],), [1, 2])
        result = check("def solve(nums):\n    return tuple(nums)\n", definition)
        self.assert_passes(result)
        self.assertNotIn("stdout", result)
        self.assertEqual(
            result["results"][0],
            {
                "passed": True,
                "input": "([1, 2],)",
                "expected": "[1, 2]",
                "actual": "(1, 2)",
            },
        )

    def test_no_return_is_none_not_success_for_numeric_zero(self):
        result = check("def solve():\n    pass\n", exercise(expected=0))
        self.assertIs(result["results"][0]["passed"], False)
        self.assertEqual(result["results"][0]["actual"], "None")
        self.assert_passes(check("def solve():\n    pass\n", exercise()))

    def test_default_comparison_rejects_boolean_integer_confusion(self):
        definition = exercise(
            cases=[
                {"args": (0,), "expected": 0},
                {"args": (1,), "expected": True},
                {"args": (2,), "expected": [0, True]},
            ]
        )
        result = check(
            "def solve(n):\n    return [False, 1, (False, 1)][n]\n", definition
        )
        self.assertTrue(all(case["passed"] is False for case in result["results"]))

    def test_wrong_missing_and_noncallable_function(self):
        for code in ("", "def other():\n    return 1\n", "solve = 42"):
            with self.subTest(code=code):
                result = check(code, exercise(expected=1))
                self.assertIn("Define a function named solve", result["error"])

    def test_syntax_import_and_top_level_exceptions(self):
        for code, message in [
            ("def broken(", "SyntaxError"),
            ("import checker_test_nonexistent_module", "ModuleNotFoundError"),
            ('raise RuntimeError("top level")', "RuntimeError: top level"),
            ("raise SystemExit(3)", "SystemExit: 3"),
        ]:
            with self.subTest(message=message):
                result = check(code, exercise())
                self.assertIn(message, result["error"])
                self.assertNotIn("timed out", result["error"])

    def test_case_exceptions_are_reported_and_later_cases_run(self):
        definition = exercise(
            cases=[
                {"args": (0,), "expected": 0},
                {"args": (1,), "expected": 2},
                {"args": (2,), "expected": 2},
            ]
        )
        code = (
            "def solve(n):\n"
            '    if n == 0: raise ValueError("oops")\n'
            '    if n == 1: raise SystemExit("stop")\n'
            "    return n\n"
        )
        result = check(code, definition)
        self.assertNotIn("error", result)
        self.assertIn("ValueError: oops", result["results"][0]["actual"])
        self.assertIn("SystemExit: stop", result["results"][1]["actual"])
        self.assertEqual(
            [case["passed"] for case in result["results"]], [False, False, True]
        )

    def test_mutations_are_independent_and_original_display_is_preserved(self):
        shared = [[1, 2]]
        cases = [{"args": (shared,), "expected": 2}, {"args": (shared,), "expected": 2}]
        code = (
            "def solve(values):\n"
            "    size = len(values[0])\n"
            "    values[0].clear()\n"
            "    return size\n"
        )
        result = check(code, exercise(cases=cases))
        self.assert_passes(result, count=2)
        self.assertTrue(
            all(case["input"] == "([[1, 2]],)" for case in result["results"])
        )
        self.assertEqual(shared, [[1, 2]])

    def test_validator_receives_pristine_not_mutated_arguments(self):
        code = "def solve(nums, target):\n    nums[:] = [2, 2]\n    return (0, 1)\n"
        result = check(code, exercise(([1, 2], 4), None, "two_sum"))
        self.assertIs(result["results"][0]["passed"], False)
        self.assertEqual(result["results"][0]["input"], "([1, 2], 4)")

    def test_all_validator_metadata_is_used_in_worker(self):
        examples = [
            ("two_sum", ([1, 2, 3, 4], 5), (0, 3), "(2, 1)"),
            (
                "group_anagrams",
                (["ab", "ba", "x"],),
                [["ab", "ba"], ["x"]],
                '(("x",), ("ba", "ab"))',
            ),
            (
                "three_sum",
                ([-1, -1, 0, 1, 2],),
                [(-1, -1, 2), (-1, 0, 1)],
                "([1, 0, -1], [2, -1, -1])",
            ),
            (
                "merge_intervals",
                ([(1, 3), (2, 6), (8, 10)],),
                [[1, 6], [8, 10]],
                "([8, 10], [1, 6])",
            ),
            ("top_k_frequent", ([1, 1, 2, 2, 3, 3], 2), [1, 2], "(3, 2)"),
            ("binary_search", ([1, 2, 2, 2], 2), 1, "3"),
        ]
        for name, args, expected, answer in examples:
            with self.subTest(validator=name):
                self.assert_passes(
                    check(
                        "def solve(*args):\n    return " + answer + "\n",
                        exercise(args, expected, name),
                    )
                )

    def test_invalid_return_types_fail_without_comparison_or_repr_execution(self):
        code = (
            "class Pretend:\n"
            "    def __eq__(self, other): return [True]\n"
            '    def __bool__(self): raise AssertionError("truth conversion")\n'
            "    def __repr__(self):\n"
            "        while True: pass\n"
            "def solve(): return Pretend()\n"
        )
        result = check(code, exercise(expected=1))
        self.assertIs(result["results"][0]["passed"], False)
        self.assertIn("Pretend", result["results"][0]["actual"])

    def test_unknown_validator_and_invalid_starter(self):
        result = check(
            "def solve(): return 1", exercise(expected=1, validator="unknown")
        )
        self.assertIn("Unknown exercise validator", result["error"])
        definition = exercise()
        definition["starter"] = "value = 1"
        result = check("def solve(): pass", definition)
        self.assertIn("Exercise starter must define a function", result["error"])

    def test_stdout_and_stderr_capture_top_level_and_cases_in_order(self):
        code = (
            "import sys\n"
            'print("loaded")\n'
            "def solve():\n"
            '    print("debug: café 🙂")\n'
            '    print("warning", file=sys.stderr)\n'
            "    return 7\n"
        )
        result = check(code, exercise(expected=7))
        self.assert_passes(result)
        self.assertEqual(result["stdout"], "loaded\ndebug: café 🙂\nwarning\n")

    def test_print_debugging_survives_top_level_and_case_errors(self):
        result = check(
            'print("before import")\nimport checker_test_nonexistent_module', exercise()
        )
        self.assertIn("ModuleNotFoundError", result["error"])
        self.assertEqual(result["stdout"], "before import\n")
        result = check(
            'def solve():\n    print("before error")\n    raise ValueError("oops")',
            exercise(),
        )
        self.assertIn("ValueError", result["results"][0]["actual"])
        self.assertEqual(result["stdout"], "before error\n")

    def test_huge_output_is_bounded_and_does_not_block(self):
        code = (
            "import sys\n"
            "def solve():\n"
            '    sys.stdout.write("🙂" * 1000000)\n'
            '    sys.stderr.write("x" * 1000000)\n'
            "    return 1\n"
        )
        result = check(code, exercise(expected=1))
        self.assert_passes(result)
        self.assertIn("[output truncated]", result["stdout"])
        self.assertLessEqual(
            len(result["stdout"].encode("utf-8")),
            checker._MAX_OUTPUT_BYTES + len(checker._OUTPUT_TRUNCATED) + 3,
        )

    def test_return_representations_and_exception_messages_are_bounded(self):
        for answer in (
            '"x" * 1000000',
            '["x" * 10000] * 100000',
            'b"x" * 1000000',
            "10 ** 100000",
        ):
            with self.subTest(answer=answer):
                result = check(
                    "def solve():\n    return " + answer, exercise(expected=0)
                )
                case = result["results"][0]
                self.assertIs(case["passed"], False)
                self.assertLessEqual(len(case["actual"]), checker._MAX_REPR_CHARS)
        result = check('def solve():\n    raise ValueError("x" * 1000000)', exercise())
        text = result["results"][0]["actual"]
        self.assertIn("ValueError", text)
        self.assertIn("[truncated]", text)
        self.assertLessEqual(len(text), checker._MAX_TRACEBACK_CHARS)

    def test_input_and_stdin_fail_without_waiting_for_interaction(self):
        examples = [
            ('def solve(): return input("prompt: ")', False),
            ("import sys\ndef solve(): return sys.stdin.read()", False),
            ("import sys\ndef solve(): return sys.stdin.readline()", False),
            ('input("top-level prompt: ")\ndef solve(): pass', True),
        ]
        for code, top_level in examples:
            with self.subTest(code=code):
                result = check(code, exercise(), timeout=3)
                text = result["error"] if top_level else result["results"][0]["actual"]
                self.assertIn("EOFError", text)
                self.assertIn("Use the function arguments", text)
                self.assertNotIn("timed out", text)

    def test_function_infinite_loop_times_out_and_preserves_prints(self):
        code = 'def solve():\n    print("entered loop")\n    while True: pass\n'
        started = time.monotonic()
        result = check(code, exercise(), timeout=1.5)
        self.assertIn("timed out", result["error"])
        self.assertEqual(result["stdout"], "entered loop\n")
        self.assertLess(time.monotonic() - started, 3)

    def test_top_level_infinite_loop_times_out(self):
        started = time.monotonic()
        result = check("while True: pass\ndef solve(): pass", exercise(), timeout=0.5)
        self.assertIn("timed out", result["error"])
        self.assertNotIn("exited unexpectedly", result["error"])
        self.assertLess(time.monotonic() - started, 2)

    def test_abrupt_exit_is_not_misreported_as_a_timeout(self):
        for status in (0, 7):
            with self.subTest(status=status):
                code = (
                    f'import os, sys\nprint("before exit", file=sys.stderr)\n'
                    f"os._exit({status})\n"
                )
                started = time.monotonic()
                result = check(code, exercise(), timeout=5)
                self.assertIn(f"exit code {status}", result["error"])
                self.assertIn("without a result", result["error"])
                self.assertNotIn("timed out", result["error"])
                self.assertEqual(result["stdout"], "before exit\n")
                self.assertLess(time.monotonic() - started, 3)

    def test_invalid_timeout_values(self):
        for timeout in (
            0,
            -1,
            False,
            True,
            float("inf"),
            float("nan"),
            None,
            "bad",
            10**1000,
        ):
            with self.subTest(timeout=timeout):
                result = check("def solve(): pass", exercise(), timeout=timeout)
                self.assertIn("positive, finite", result["error"])

    def test_start_failure_releases_queue_and_unstarted_process(self):
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        process = mock.Mock(pid=None)
        process.start.side_effect = OSError("cannot create child")
        process.is_alive.return_value = False
        with mock.patch.object(
            context, "Queue", return_value=output
        ), mock.patch.object(context, "Process", return_value=process), mock.patch(
            "practice.checker.multiprocessing.get_context", return_value=context
        ), mock.patch.object(
            output, "close", wraps=output.close
        ) as close, mock.patch.object(
            output, "join_thread", wraps=output.join_thread
        ) as join_thread:
            result = check("def solve(): pass", exercise())
        self.assertIn("Could not start checker process", result["error"])
        self.assertIn("cannot create child", result["error"])
        process.close.assert_called_once_with()
        process.join.assert_not_called()
        close.assert_called_once_with()
        join_thread.assert_called_once_with()

    def test_process_startup_counts_against_wall_timeout(self):
        context = multiprocessing.get_context("spawn")
        process = mock.Mock(pid=None)
        clock = mock.Mock(return_value=0)
        process.start.side_effect = lambda: setattr(clock, "return_value", 2)
        with mock.patch.object(context, "Process", return_value=process), mock.patch(
            "practice.checker.multiprocessing.get_context", return_value=context
        ), mock.patch("practice.checker.time.monotonic", clock), mock.patch(
            "practice.checker._wait_for_result", wraps=checker._wait_for_result
        ) as wait:
            result = check("def solve(): pass", exercise(), timeout=1)
        self.assertIn("timed out", result["error"])
        process.start.assert_called_once_with()
        self.assertTrue(
            wait.called, "Startup should return, then observe the expired deadline"
        )
        process.close.assert_called_once_with()

    def test_process_construction_failure_releases_existing_queue(self):
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        with mock.patch.object(
            context, "Queue", return_value=output
        ), mock.patch.object(
            context, "Process", side_effect=OSError("construction failed")
        ), mock.patch(
            "practice.checker.multiprocessing.get_context", return_value=context
        ), mock.patch.object(
            output, "close", wraps=output.close
        ) as close, mock.patch.object(
            output, "join_thread", wraps=output.join_thread
        ) as join_thread:
            result = check("def solve(): pass", exercise())
        self.assertIn("Could not start checker process", result["error"])
        self.assertIn("construction failed", result["error"])
        close.assert_called_once_with()
        join_thread.assert_called_once_with()

    def test_context_or_queue_creation_failure_returns_an_actionable_error(self):
        with mock.patch(
            "practice.checker.multiprocessing.get_context", side_effect=OSError("no context")
        ):
            result = check("def solve(): pass", exercise())
        self.assertIn("Could not start checker process", result["error"])
        self.assertIn("no context", result["error"])
        context = multiprocessing.get_context("spawn")
        with mock.patch.object(
            context, "Queue", side_effect=OSError("no queue")
        ), mock.patch("practice.checker.multiprocessing.get_context", return_value=context):
            result = check("def solve(): pass", exercise())
        self.assertIn("Could not start checker process", result["error"])
        self.assertIn("no queue", result["error"])

    def test_result_read_failure_releases_resources(self):
        context = multiprocessing.get_context("spawn")
        process = mock.Mock(pid=None)
        with mock.patch.object(context, "Process", return_value=process), mock.patch(
            "practice.checker.multiprocessing.get_context", return_value=context
        ), mock.patch("practice.checker._wait_for_result", side_effect=OSError("broken queue")):
            result = check("def solve(): pass", exercise())
        self.assertIn("Could not read checker process result", result["error"])
        self.assertIn("broken queue", result["error"])
        process.close.assert_called_once_with()

    def test_release_handles_exit_racing_with_terminate(self):
        process, output = mock.Mock(pid=123), mock.Mock()
        process.is_alive.side_effect = [True, False]
        process.terminate.side_effect = OSError("process exited during terminate")
        checker._release(process, output)
        process.kill.assert_called_once_with()
        process.close.assert_called_once_with()
        output.close.assert_called_once_with()
        output.join_thread.assert_called_once_with()

    def test_release_escalates_to_kill_when_terminate_is_not_enough(self):
        process, output = mock.Mock(pid=123), mock.Mock()
        process.is_alive.side_effect = [True, True, False]
        checker._release(process, output)
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        process.close.assert_called_once_with()
        self.assertEqual(process.join.call_count, 3)
        output.close.assert_called_once_with()
        output.join_thread.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
