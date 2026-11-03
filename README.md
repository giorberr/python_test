# Python Algorithm Practice

A local desktop app for learning Python and practicing algorithms through editable exercises, automated feedback, and timed challenges.

## Repository layout

```text
app.py                   # Start the desktop app
practice/                # Application source code
    app.py               # Desktop interface and mock sessions
    editor.py            # Code editor and indentation shortcuts
    exercises.py         # Editable problem descriptions, starters, and test cases
    checker.py           # Runs your code in a separate process
    validators.py        # Checks answers, including equivalent outputs
    progress.py          # Saves and recovers drafts and completion history
tests/                   # Automated tests for the app and backend
data/                    # Personal progress and recovery backups (ignored by Git)
README.md                # Setup, usage, and project guide
```

- **To practice:** run `python app.py` and edit your solution inside the app.
- **To change the curriculum:** edit `practice/exercises.py`.
- **To change how answers are checked:** edit `practice/validators.py` or `practice/checker.py`.
- **To back up your work:** copy `data/practice_progress.json`.

There are no third-party Python dependencies to install.

## Start

Install Python 3.9 or newer with Tkinter (included in the standard Windows Python installer), open a terminal in this folder, and run:

```sh
python app.py
```

Choose an exercise, edit its starter function, and select **Run tests**. Results show each case and, for failures, a valid expected example and your actual value or an exception. `print()` output and Python stderr appear below the results. Output and long values are truncated to keep the interface responsive; `input()` is not available—use the function arguments.

### Editor shortcuts

- **Tab:** insert spaces up to the next four-column stop. With text selected, indent the selected lines by four spaces without replacing the code.
- **Shift+Tab:** remove up to four columns of indentation from the current or selected lines.
- **Ctrl+Tab / Ctrl+Shift+Tab:** move keyboard focus out of the editor, forward or backward.
- Indentation changes can be undone and redone as single actions. On lines you indent or outdent, existing leading tabs are converted to equivalent spaces using Python's eight-column tab stops; tabs inside the code itself are not rewritten.

Drafts are saved when you switch exercises, run tests, select **Save draft**, or close the app. `data/practice_progress.json` stores drafts and historical completion marks separately from the source code. Existing progress was moved there during the reorganization without changing its contents. Saves replace the file atomically; malformed data is backed up as `data/practice_progress.corrupt-<timestamp>.json` before starting fresh. If a backup cannot be made, saving is blocked rather than overwriting the original. A failed save blocks exercise switching and prompts before closing.

A completion mark means a submitted draft passed all provided cases at least once. Editing or resetting that draft does not erase the historical mark. It does not prove complexity, compliance with restrictions such as no division, or correctness for every possible input.

Choose a mock and select **Start 70-minute mock** to focus on its two exercises. Existing drafts and completion marks remain available, so reset drafts first if you want a fresh attempt. The timer is a practice aid: it runs only while the app is open, is not restored after closing, and returns to normal practice mode when it expires. It does not independently score a mock or prevent later attempts.

The curriculum contains all 15 requested exercises and 152 cases. Each exercise specifies its input/output conventions, including additional empty-input cases. Equivalent answers are accepted for Two Sum, Binary Search, Group Anagrams, 3Sum, Merge Intervals, and Top K Frequent Elements: order and list/tuple differences do not cause false failures where the problem allows them. Expected results shown in these exercises are examples, not the only permitted ordering or answer. Boolean results must actually be `True`/`False`, and integer results must be integers rather than booleans or floats.

The tree exercise deliberately accepts a compact serialized level-order list rather than a `TreeNode`; its description explains the encoding. `practice/exercises.py` holds descriptions, starter code, and cases; `practice/validators.py` defines answer equivalence; `practice/checker.py` runs submissions; `practice/progress.py` handles storage; `practice/app.py` provides the interface. The root `app.py` is only a launcher. You can edit the exercise definitions to change practice content.

## Security

**Only run code you trust.** The checker uses a separate process and a five-second overall timeout to help stop infinite loops, but it is **not a security sandbox**. Submitted Python has the same file, network, and system permissions as your user account. It can also spawn processes or consume resources. Do not expose this app to untrusted submissions.

## Verification

Run these commands from the repository root (the folder containing this README).

Full automated suite:

```sh
python -m unittest discover -v
```

To run only the backend checks:

```sh
python -m unittest tests.test_checker tests.test_exercises -v
```

The suite checks every exercise's expected values against independent reference algorithms, runs reference and deliberately incorrect submissions, covers checker failures/timeouts/output limits, verifies safe progress-file recovery, and exercises real Tk widgets and mock-timer expiry. Tests use temporary progress files and do not modify your saved practice. Tk tests are skipped if no display is available. The suite was verified on Windows with Python 3.15 and Tk 9; other supported Python/Tk versions were not tested.
