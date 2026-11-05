"""Real Tk widget smoke tests; all progress writes use temporary directories."""

import json
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import font
from unittest.mock import patch

from practice import app
from practice.editor import CodeEditor
from practice.exercises import EXERCISES
from practice.theme import DARK_COLORS


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
        self.assertEqual(self.gui.run_button["text"], "Run tests")

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

    def test_dark_theme_colors_and_text_selection(self):
        colors = DARK_COLORS
        self.assertEqual(self.gui.style.theme_use(), "clam")
        self.assertEqual(self.root["background"], colors["background"])
        for widget in (self.gui.listbox, self.gui.editor, self.gui.results):
            with self.subTest(widget=widget.winfo_class()):
                self.assertEqual(widget["background"], colors["surface"])
                self.assertEqual(widget["foreground"], colors["foreground"])
                self.assertEqual(widget["selectbackground"], colors["selection"])
                self.assertEqual(widget["selectforeground"], colors["foreground"])
                self.assertEqual(widget["highlightcolor"], colors["accent"])
        self.assertEqual(self.gui.editor["insertbackground"], colors["foreground"])
        self.assertEqual(
            self.gui.editor["inactiveselectbackground"], colors["selection"]
        )
        self.assertEqual(str(self.gui.results["state"]), "disabled")
        for text in (self.gui.editor, self.gui.results):
            self.assertEqual(text.frame["background"], colors["background"])
            self.assertIsInstance(text.vbar, app.ttk.Scrollbar)
            self.assertEqual(str(text.vbar["takefocus"]), "0")

    def test_themed_text_panes_scroll_in_both_directions(self):
        self.root.deiconify()
        for text in (self.gui.editor, self.gui.results):
            with self.subTest(pane=str(text)):
                text.configure(state="normal")
                text.delete("1.0", "end")
                text.insert("1.0", "line\n" * 200)
                self.root.update()
                text.yview_moveto(1.0)
                self.root.update()
                self.assertGreater(text.yview()[0], 0.0)
                self.assertEqual(text.vbar.get(), text.yview())
                self.assertAlmostEqual(text.vbar.get()[1], 1.0)
                self.root.tk.call(text.vbar["command"], "moveto", 0)
                self.root.update()
                self.assertEqual(text.yview()[0], 0.0)

    def test_dark_theme_control_states(self):
        style = self.gui.style
        for name, option, state, color in (
            ("TFrame", "background", (), "background"),
            ("TFrame", "background", ("disabled",), "background"),
            ("TFrame", "background", ("active",), "hover"),
            (".", "selectbackground", ("!focus",), "selection"),
            (".", "selectforeground", ("!focus",), "foreground"),
            ("TLabel", "foreground", (), "foreground"),
            ("Muted.TLabel", "foreground", (), "muted"),
            ("TButton", "background", (), "surface"),
            ("TButton", "background", ("active",), "hover"),
            ("TButton", "background", ("pressed",), "pressed"),
            ("TButton", "lightcolor", ("pressed",), "border"),
            ("TButton", "darkcolor", ("pressed",), "border"),
            ("TButton", "foreground", ("disabled",), "disabled"),
            ("TCombobox", "fieldbackground", ("readonly",), "surface"),
            ("TCombobox", "foreground", ("readonly",), "foreground"),
            ("Vertical.TScrollbar", "background", (), "border"),
            ("Vertical.TScrollbar", "background", ("active",), "hover"),
        ):
            with self.subTest(style=name, option=option, state=state):
                self.assertEqual(style.lookup(name, option, state), DARK_COLORS[color])

    def test_run_button_has_accessible_primary_states(self):
        self.assertEqual(self.gui.run_button["style"], "Primary.TButton")
        style = self.gui.style
        for option, state, color in (
            ("background", (), "accent"),
            ("foreground", (), "background"),
            ("focuscolor", (), "background"),
            ("background", ("active",), "accent_hover"),
            ("background", ("pressed",), "accent_pressed"),
            ("background", ("disabled",), "surface"),
            ("foreground", ("disabled",), "disabled"),
        ):
            with self.subTest(option=option, state=state):
                self.assertEqual(
                    style.lookup("Primary.TButton", option, state), DARK_COLORS[color]
                )

    def test_workspace_divider_can_be_dragged_without_changing_the_draft(self):
        self.root.deiconify()
        self.root.update()
        workspace = self.gui.workspace
        self.assertEqual(str(workspace["orient"]), "vertical")
        self.assertEqual(len(workspace.panes()), 2)
        editor_height = self.gui.editor.winfo_height()
        results_height = self.gui.results.winfo_height()
        self.assertGreater(editor_height, results_height)
        source = self.gui.editor.get("1.0", "end-1c")
        sash = workspace.sashpos(0)
        workspace_height = workspace.winfo_height()
        target = round(workspace_height * 0.45)
        workspace.event_generate("<ButtonPress-1>", x=20, y=sash + 1)
        workspace.event_generate("<B1-Motion>", x=20, y=target + 1)
        workspace.event_generate("<ButtonRelease-1>", x=20, y=target + 1)
        self.root.update()
        self.assertAlmostEqual(workspace.sashpos(0), target, delta=2)
        self.assertLess(self.gui.editor.winfo_height(), editor_height)
        self.assertGreater(self.gui.results.winfo_height(), results_height)
        self.assertTrue(self.gui.run_button.winfo_ismapped())
        self.assertEqual(self.gui.editor.get("1.0", "end-1c"), source)
        # A wrapped description can resize the workspace, but must not reset
        # the chosen split; native pane weights distribute that height change.
        self.gui.show_exercise(1)
        self.root.update()
        expected = target + (workspace.winfo_height() - workspace_height) * 3 / 4
        self.assertAlmostEqual(workspace.sashpos(0), expected, delta=2)

    def test_combobox_popup_uses_dark_colors(self):
        popup = self.root.tk.call(
            "ttk::combobox::PopdownWindow", str(self.gui.mock_choice)
        )
        for option, color in (
            ("background", "surface"),
            ("foreground", "foreground"),
            ("selectbackground", "selection"),
            ("selectforeground", "foreground"),
        ):
            with self.subTest(option=option):
                self.assertEqual(
                    self.root.tk.call(f"{popup}.f.l", "cget", f"-{option}"),
                    DARK_COLORS[color],
                )

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
        self.assertEqual(self.gui.run_button["text"], "Running…")
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


class DisplayLayoutTests(unittest.TestCase):
    def test_display_scale_changes_pixels_not_font_points_or_character_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            for scale in (1.0, 1.25, 1.5, 2.0):
                with self.subTest(scale=scale):
                    try:
                        root = tk.Tk()
                    except tk.TclError as error:
                        self.skipTest(f"Tk display is unavailable: {error}")
                    root.withdraw()
                    gui = None
                    try:
                        root.tk.call("tk", "scaling", scale * 96 / 72)
                        tk_scaling = float(root.tk.call("tk", "scaling"))
                        with patch.object(
                            app, "DATA_FILE", Path(directory) / "progress.json"
                        ), patch("practice.display.sys.platform", "win32"), patch(
                            "practice.display._work_area_bounds",
                            return_value=(0, 0, 5000, 4000),
                        ):
                            gui = app.PracticeApp(root)
                        root.update_idletasks()
                        self.assertEqual(gui.display.scale, scale)
                        self.assertEqual(gui.display.pixels(10), round(10 * scale))
                        self.assertEqual(
                            root.winfo_pixels(root.tk.splitlist(
                                gui.style.lookup("TButton", "padding")
                            )[0]),
                            round(5 * scale),
                        )
                        self.assertEqual(
                            root.winfo_pixels(
                                gui.style.lookup("Vertical.TScrollbar", "arrowsize")
                            ),
                            round(14 * scale),
                        )
                        self.assertEqual(font.Font(root, font=gui.editor["font"])["size"], 11)
                        self.assertEqual(font.Font(root, font=gui.results["font"])["size"], 10)
                        self.assertEqual(int(gui.listbox["width"]), 33)
                        self.assertEqual(int(gui.editor["height"]), 14)
                        assert isinstance(gui.editor, CodeEditor)
                        self.assertEqual(gui.editor._gutter_padding, round(8 * scale))
                        self.assertEqual(int(gui.results["height"]), 5)
                        root.deiconify()
                        root.update()
                        self.assertGreater(
                            gui.editor.winfo_height(), gui.results.winfo_height()
                        )
                        self.assertTrue(gui.editor.gutter.winfo_ismapped())
                        self.assertTrue(gui.run_button.winfo_ismapped())
                        self.assertAlmostEqual(
                            float(root.tk.call("tk", "scaling")), tk_scaling
                        )
                    finally:
                        if gui is not None:
                            gui.close()
                        else:
                            root.destroy()


if __name__ == "__main__":
    unittest.main()
