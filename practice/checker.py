"""Run local, trusted practice submissions in a separate Python process.

This is not a security sandbox: submissions have the user's permissions.
Python stdout/stderr are captured together, including before a crash or timeout.
"""

import ast
import contextlib
import copy
import io
import math
import multiprocessing
import queue
import reprlib
import sys
import threading
import time
import traceback
from typing import Any

from .validators import get_validator

_MAX_OUTPUT_BYTES = 8192
_MAX_REPR_CHARS = 2000
_MAX_TRACEBACK_CHARS = 4000
_OUTPUT_TRUNCATED = "\n[output truncated]\n"


def _truncate(text, limit):
    marker = " ... [truncated]"
    return text if len(text) <= limit else text[: limit - len(marker)] + marker


class _LimitedRepr(reprlib.Repr):
    def __init__(self):
        super().__init__()
        self.maxlevel = 3
        self.maxlist = self.maxtuple = self.maxdict = 6
        self.maxset = self.maxfrozenset = 6
        self.maxstring = 256
        self.maxother = 160

    def repr1(self, x, level):
        if type(x) not in (
            type(None),
            bool,
            int,
            float,
            complex,
            str,
            bytes,
            list,
            tuple,
            dict,
            set,
            frozenset,
        ):
            # Debugging a return value must not execute its arbitrary __repr__.
            return f"<{type(x).__name__[:80]} object>"
        return super().repr1(x, level)

    def repr_int(self, x, level):
        if x.bit_length() > 1024:
            return f"<int with {x.bit_length()} bits>"
        return _truncate(repr(x), self.maxother)

    def repr_bytes(self, value, level):
        if len(value) > self.maxstring:
            return repr(value[: self.maxstring]) + "..."
        return repr(value)


def _safe_repr(value):
    try:
        return _truncate(_LimitedRepr().repr(value), _MAX_REPR_CHARS)
    except BaseException:
        return "<value could not be represented>"


def _exception_text(limit=4):
    try:
        return _truncate(traceback.format_exc(limit=limit), _MAX_TRACEBACK_CHARS)
    except BaseException:
        return "An exception occurred, but its traceback could not be formatted."


class _NoInput(io.TextIOBase):
    def readable(self):
        return True

    def read(self, *args, **kwargs):
        raise EOFError(
            "Interactive stdin is unavailable. Use the function arguments instead."
        )

    readline = read


class _CapturedOutput(io.TextIOBase):
    """Bounded shared storage keeps diagnostics available if the child is killed."""

    def __init__(self, state):
        super().__init__()
        self._data, self._size, self._truncated = state
        self._lock = threading.Lock()

    encoding = "utf-8"

    def writable(self):
        return True

    def write(self, text):
        if not isinstance(text, str):
            raise TypeError("write() requires a string")
        if self.closed:
            raise ValueError("write to closed output")
        with self._lock:
            size = self._size.value
            remaining = len(self._data) - size
            if remaining and text:
                # Slice before encoding, so even a huge print allocates only a small buffer.
                encoded = text[:remaining].encode("utf-8", errors="replace")
                chunk = encoded[:remaining]
                self._data[size : size + len(chunk)] = chunk
                self._size.value = size + len(chunk)
                if len(encoded) > remaining or len(text) > remaining:
                    self._truncated.value = 1
            elif text:
                self._truncated.value = 1
        return len(text)


def _captured_text(state):
    data, size, truncated = state
    text = bytes(data[: size.value]).decode("utf-8", errors="replace")
    return text + (_OUTPUT_TRUNCATED if truncated.value else "")


def _worker(code, exercise, output, capture_state):
    capture = _CapturedOutput(capture_state)
    original_stdin = sys.stdin
    sys.stdin = _NoInput()
    try:
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            try:
                tree = ast.parse(exercise["starter"])
                name = next(
                    (
                        node.name
                        for node in tree.body
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ),
                    None,
                )
                if name is None:
                    raise ValueError("Exercise starter must define a function.")
                validator = get_validator(exercise.get("validator"))
                namespace = {"__name__": "__submission__"}
                exec(compile(code, "<your solution>", "exec"), namespace)
                function = namespace.get(name)
                if not callable(function):
                    raise ValueError(f"Define a function named {name}.")
                results = []
                for case in exercise["cases"]:
                    entry = {
                        "passed": False,
                        "input": _safe_repr(case["args"]),
                        "expected": _safe_repr(case["expected"]),
                    }
                    try:
                        args = copy.deepcopy(case["args"])
                        actual = function(*args)
                        # Validate against pristine arguments, not inputs mutated by the solution.
                        entry["passed"] = (
                            validator(actual, case["args"], case["expected"]) is True
                        )
                        entry["actual"] = _safe_repr(actual)
                    except BaseException:
                        entry["actual"] = _exception_text()
                    results.append(entry)
                result = {"results": results}
            except BaseException:
                result = {"error": _exception_text(limit=5)}
            output.put(result)
    finally:
        sys.stdin = original_stdin


def _wait_for_result(output, process, deadline, timeout):
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"error": f"Checker timed out after {timeout} seconds."}
        try:
            return output.get(timeout=min(remaining, 0.05))
        except queue.Empty:
            if process.exitcode is not None:
                # A normally exiting Queue writer flushes its feeder before exit.
                try:
                    return output.get_nowait()
                except queue.Empty:
                    return {
                        "error": "Checker process exited unexpectedly without a result "
                        f"(exit code {process.exitcode})."
                    }


def _release(process, output):
    try:
        if process is not None:
            for action, grace in ((None, 0.05), ("terminate", 0.2), ("kill", 0.2)):
                try:
                    if process.pid is None:
                        break
                    if action is not None:
                        getattr(process, action)()
                    process.join(timeout=grace)
                    if not process.is_alive():
                        break
                except (OSError, ValueError, AssertionError):
                    # Exit can race with terminate/join; still attempt cleanup/escalation.
                    continue
            try:
                process.close()
            except (OSError, ValueError):
                pass
    finally:
        if output is not None:
            output.close()
            output.join_thread()


def check(code, exercise, timeout: Any = 5) -> dict[str, Any]:
    """Return {'results': [...]} or {'error': str}, plus optional captured 'stdout'.

    Case input/expected/actual fields remain bounded display strings. The wall
    timeout covers process startup, submission top-level code, and all cases.
    Isolation is for responsiveness, not security; only run trusted local code.
    """
    started = time.monotonic()
    try:
        valid_timeout = (
            type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
        )
    except OverflowError:
        valid_timeout = False
    if not valid_timeout:
        return {
            "error": "Checker timeout must be a positive, finite number of seconds."
        }
    deadline = started + timeout
    process = output = capture_state = None
    try:
        try:
            context = multiprocessing.get_context("spawn")
            output = context.Queue(maxsize=1)
            capture_state = (
                context.RawArray("B", _MAX_OUTPUT_BYTES),
                context.RawValue("i", 0),
                context.RawValue("b", 0),
            )
            process = context.Process(
                target=_worker,
                args=(code, exercise, output, capture_state),
                daemon=True,
            )
            if time.monotonic() >= deadline:
                result = {"error": f"Checker timed out after {timeout} seconds."}
            else:
                process.start()
                result = None
        except Exception:
            result = {"error": "Could not start checker process:\n" + _exception_text()}
        if result is None:
            try:
                result = _wait_for_result(output, process, deadline, timeout)
            except Exception:
                result = {
                    "error": "Could not read checker process result:\n"
                    + _exception_text()
                }
    finally:
        _release(process, output)
    if capture_state is not None:
        captured = _captured_text(capture_state)
        if captured:
            result["stdout"] = captured
    return result
