"""Real Tk widget smoke tests; all progress writes use temporary directories."""

import json
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from practice import app
from practice.editor import CodeEditor
from practice.exercises import EXERCISES


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "progress.json"
        self.file_patch = patch.object(app, "DATA_FILE", self.path)
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = (
            lambda *error: self.callback_errors.append(error)
        )
        self.gui = app.PracticeApp(self.root)
        self.addCleanup(self.destroy_root)
        self.root.update()

    def destroy_root(self):
        if not self.gui._closing:
            self.gui.close()
        self.assertEqual(self.callback_errors, [])

    def write_code(self, code):
        self.gui.editor.delete("1.0", "end")
        self.gui.editor.insert("1.0", code)

    def wait_for_run(self):
        deadline = time.monotonic() + 10
        while self.gui.running and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(
            self.gui.running, "The UI did not receive checker results in time"
        )
        self.assertEqual(str(self.gui.run_button["state"]), "normal")

    def test_widgets_and_all_exercises(self):
        self.assertIsInstance(self.gui.editor, CodeEditor)
        self.assertEqual(self.gui.listbox.size(), 15)
        for index, exercise in enumerate(EXERCISES):
            with self.subTest(exercise=exercise["id"]):
                self.assertTrue(self.gui.show_exercise(index))
                self.assertEqual(
                    self.gui.editor.get("1.0", "end-1c"), exercise["starter"]
                )
                self.assertIn(exercise["title"], self.gui.title["text"])
                self.root.update()

    def test_drafts_save_switch_and_reload(self):
        code = "def contains_duplicate(nums):\n    return len(set(nums)) != len(nums)\n# 🙂\n"
        self.write_code(code)
        self.gui.show_exercise(1)
        self.gui.show_exercise(0)
        self.assertEqual(self.gui.editor.get("1.0", "end-1c"), code)
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8"))["drafts"][
                EXERCISES[0]["id"]
            ],
            code,
        )
        self.assertEqual(self.gui.store.load()["drafts"][EXERCISES[0]["id"]], code)

    def test_undo_cannot_leak_between_exercises(self):
        self.gui.editor.insert("end", "\n# previous exercise")
        self.gui.show_exercise(1)
        try:
            self.gui.editor.edit_undo()
        except tk.TclError:
            pass
        self.assertEqual(self.gui.editor.get("1.0", "end-1c"), EXERCISES[1]["starter"])

    def test_reset_clears_draft_and_old_results(self):
        self.write_code("# old draft")
        self.gui.last_results[0] = 'old results'
        with patch('practice.app.messagebox.askyesno', return_value=True):
            self.gui.reset()
        self.assertEqual(self.gui.editor.get("1.0", "end-1c"), EXERCISES[0]["starter"])
        self.assertNotIn(0, self.gui.last_results)
        self.assertEqual(
            self.gui.store.load()["drafts"][EXERCISES[0]["id"]], EXERCISES[0]["starter"]
        )

    def test_real_async_run_output_and_completion(self):
        self.write_code(
            'def contains_duplicate(nums):\n    print("checking")\n    return len(nums) != len(set(nums))\n'
        )
        self.gui.run_tests()
        self.assertEqual(str(self.gui.run_button["state"]), "disabled")
        self.wait_for_run()
        result_text = self.gui.results.get("1.0", "end-1c")
        self.assertIn("8 / 8 tests passed", result_text)
        self.assertIn("PRINT OUTPUT", result_text)
        self.assertIn("checking", result_text)
        self.assertIn(EXERCISES[0]["id"], self.gui.store.load()["solved"])
        self.gui.show_exercise(1)
        self.gui.show_exercise(0)
        self.assertEqual(self.gui.results.get("1.0", "end-1c"), result_text)

    def test_switch_during_run_does_not_attribute_results_to_wrong_exercise(self):
        self.write_code(
            "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n"
        )
        self.gui.run_tests()
        self.gui.show_exercise(1)
        self.wait_for_run()
        self.assertIn("Write your solution", self.gui.results.get("1.0", "end-1c"))
        self.assertIn(EXERCISES[0]["id"], self.gui.data["solved"])
        self.assertNotIn(EXERCISES[1]["id"], self.gui.data["solved"])
        self.gui.show_exercise(0)
        self.assertIn("8 / 8", self.gui.results.get("1.0", "end-1c"))

    def test_checker_failure_is_displayed_and_button_reenabled(self):
        self.write_code("def broken(")
        self.gui.run_tests()
        self.wait_for_run()
        self.assertIn("SyntaxError", self.gui.results.get("1.0", "end-1c"))
        self.assertEqual(self.gui.data["solved"], [])

    def test_mock_pairs_and_expiry(self):
        with patch('practice.app.messagebox.askyesno', return_value=True):
            for label, pair in app.MOCKS.items():
                self.gui.mock_choice.set(label)
                self.gui.start_mock()
                self.assertEqual(self.gui.indices, list(pair))
                self.assertEqual(self.gui.current, pair[0])
                self.assertEqual(self.gui.listbox.size(), 2)
                assert self.gui.deadline is not None
                self.assertGreater(self.gui.deadline, time.monotonic() + 4190)
                self.gui.end_mock()
                self.assertEqual(self.gui.listbox.size(), 15)
            self.gui.start_mock()
        self.write_code("# final mock draft")
        self.gui.deadline = time.monotonic() - 1
        # Exercise the real timer callback once, avoiding a second timer chain.
        assert self.gui._tick_after is not None
        self.root.after_cancel(self.gui._tick_after)
        with patch('practice.app.messagebox.showinfo') as notification:
            self.gui.tick()
        self.assertIsNone(self.gui.deadline)
        self.assertIsNone(self.gui.mock)
        self.assertEqual(self.gui.timer_label["text"], "Practice mode")
        assert self.gui.current is not None
        self.assertEqual(
            self.gui.store.load()["drafts"][EXERCISES[self.gui.current]["id"]],
            "# final mock draft",
        )
        notification.assert_called_once()

    def test_failed_save_blocks_switch_and_accidental_close(self):
        self.write_code("# do not lose me")
        with patch.object(self.gui.store, "save", side_effect=OSError("disk full")):
            with patch("practice.app.messagebox.showerror") as error, patch(
                "practice.app.messagebox.askyesno", return_value=False
            ):
                self.assertFalse(self.gui.show_exercise(1))
                self.assertEqual(self.gui.current, 0)
                self.gui.close()
                self.assertFalse(self.gui._closing)
                self.assertEqual(
                    self.gui.editor.get("1.0", "end-1c"), "# do not lose me"
                )
                self.assertEqual(error.call_count, 2)

    def test_reset_invalidates_pending_result_display(self):
        self.write_code(
            "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n"
        )
        self.gui.run_tests()
        with patch("practice.app.messagebox.askyesno", return_value=True):
            self.gui.reset()
        self.wait_for_run()
        self.assertNotIn(0, self.gui.last_results)
        self.assertIn("Draft reset", self.gui.results.get("1.0", "end-1c"))
        self.assertEqual(self.gui.editor.get("1.0", "end-1c"), EXERCISES[0]["starter"])
        self.assertIn(EXERCISES[0]["id"], self.gui.data["solved"])

    def test_mock_start_saves_once_before_transition(self):
        self.gui.mock_choice.set(list(app.MOCKS)[1])
        with patch("practice.app.messagebox.askyesno", return_value=True):
            with patch.object(
                self.gui.store,
                "save",
                side_effect=[None, PermissionError("second save failed")],
            ) as save:
                self.gui.start_mock()
                self.assertEqual(save.call_count, 1)
        self.assertEqual(self.gui.current, 6)
        self.assertEqual(self.gui.indices, [6, 9])
        self.assertEqual(self.gui.listbox.curselection(), (0,))

    def test_failed_mock_save_leaves_practice_unchanged(self):
        with patch("practice.app.messagebox.askyesno", return_value=True), patch(
            "practice.app.messagebox.showerror"
        ):
            with patch.object(
                self.gui.store, "save", side_effect=PermissionError("save failed")
            ):
                self.gui.start_mock()
        self.assertIsNone(self.gui.mock)
        self.assertIsNone(self.gui.deadline)
        self.assertEqual(self.gui.current, 0)
        self.assertEqual(self.gui.listbox.size(), 15)

    def test_responsive_description_wrapping(self):
        self.gui.resize_description(type("Resize", (), {"width": 450})())
        self.assertLessEqual(int(self.gui.description["wraplength"]), 450)
        self.assertLessEqual(int(self.gui.title["wraplength"]), 450)


if __name__ == "__main__":
    unittest.main()
