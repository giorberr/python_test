"""Exercise editor bindings in real, focused Tk widgets, without app data."""

import tkinter as tk
import unittest

from practice.editor import CodeEditor


class EditorKeyTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.callback_errors = []
        self.addCleanup(self.destroy_root)
        self.root.report_callback_exception = (
            lambda kind, error, traceback: self.callback_errors.append(
                f"{kind.__name__}: {error}"
            )
        )
        self.root.title("Editor key-event tests")
        self.root.geometry("640x420+40+40")
        self.before = tk.Entry(self.root, takefocus=True, exportselection=False)
        self.before.pack(fill="x")
        self.editor = CodeEditor(
            self.root,
            width=60,
            height=8,
            wrap="none",
            takefocus=True,
            exportselection=False,
        )
        self.editor.pack(fill="both", expand=True)
        self.after = tk.Entry(self.root, takefocus=True, exportselection=False)
        self.after.pack(fill="x")
        self.root.update()
        self.assertTrue(self.editor.winfo_ismapped())
        self.focus(self.editor)

    def destroy_root(self):
        try:
            self.root.destroy()
        finally:
            self.assertEqual(self.callback_errors, [], "Tk binding callback failed")

    def focus(self, widget):
        widget.focus_force()
        self.root.update()
        self.assertEqual(self.root.focus_get(), widget)

    def load(self, text, caret="1.0", selection=None):
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.tag_remove("sel", "1.0", "end")
        self.editor.mark_set("insert", caret)
        if selection is not None:
            self.editor.tag_add("sel", *selection)
            self.assertTrue(self.editor.tag_ranges("sel"))
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.focus(self.editor)

    def key(self, sequence, widget=None):
        widget = self.editor if widget is None else widget
        self.assertTrue(widget.winfo_ismapped())
        self.assertEqual(self.root.focus_get(), widget)
        # Observe delivery before widget/class bindings without replacing either.
        delivered = []
        probe = "EditorKeyTestDelivery"
        tags = widget.bindtags()
        widget.bind_class(
            probe, "<KeyPress>",
            lambda event: delivered.append((event.keysym, event.keycode)),
        )
        widget.bindtags((probe,) + tags)
        try:
            widget.event_generate(sequence, when="now")
            self.root.update()
        finally:
            widget.bindtags(tags)
            widget.unbind_class(probe, "<KeyPress>")
        self.assertEqual(self.callback_errors, [])
        self.assertEqual(len(delivered), 1, f"No unique key event for {sequence}")
        windowing = self.root.tk.call("tk", "windowingsystem")
        if (
            "ISO_Left_Tab" in sequence
            and windowing == "win32"
            and delivered[0] == ("??", 0)
        ):
            version = self.root.tk.call("package", "provide", "Tk")
            self.skipTest(
                f"Windows Tk {version} cannot synthesize {sequence}: "
                "delivered keysym '??', keycode 0"
            )
        self.assertNotEqual(delivered[0][0], "??", f"Unrecognized {sequence}")

    def text(self):
        return self.editor.get("1.0", "end-1c")

    def selection(self):
        return tuple(str(index) for index in self.editor.tag_ranges("sel"))

    def assert_selected_lines(self, first, last):
        ranges = self.selection()
        self.assertEqual(len(ranges), 2, "Indentation lost the selection")
        start_line = int(ranges[0].split(".")[0])
        end_line, end_column = map(int, ranges[1].split("."))
        if end_column == 0 and end_line > start_line:
            end_line -= 1
        self.assertEqual((start_line, end_line), (first, last))

    def assert_no_history(self):
        with self.assertRaises(tk.TclError):
            self.editor.edit_undo()

    def assert_single_edit(self, before, after):
        self.assertEqual(self.text(), after)
        self.editor.edit_undo()
        self.assertEqual(self.text(), before, "One undo must restore the whole edit")
        self.assert_no_history()
        self.editor.edit_redo()
        self.assertEqual(self.text(), after, "Redo must restore the whole edit")
        with self.assertRaises(tk.TclError):
            self.editor.edit_redo()

    def assert_history(self, snapshots):
        for expected in reversed(snapshots[:-1]):
            self.editor.edit_undo()
            self.assertEqual(self.text(), expected)
        self.assert_no_history()
        for expected in snapshots[1:]:
            self.editor.edit_redo()
            self.assertEqual(self.text(), expected)
        with self.assertRaises(tk.TclError):
            self.editor.edit_redo()

    def ordinary_text(self, text, caret, selection=None):
        widget = tk.Text(
            self.root, height=2, undo=True, takefocus=True, exportselection=False
        )
        widget.pack(fill="x")
        widget.insert("1.0", text)
        widget.mark_set("insert", caret)
        if selection is not None:
            widget.tag_add("sel", *selection)
        self.root.update()
        self.focus(widget)
        return widget

    def test_tab_suppresses_the_text_class_raw_tab_insertion(self):
        plain = self.ordinary_text("body", "1.1")
        self.assertIn("Text", plain.bindtags())
        self.key("<Tab>", plain)
        self.assertEqual(plain.get("1.0", "end-1c"), "b\tody")

        self.load("body", "1.1")
        self.key("<Tab>")
        self.assertEqual(self.editor.index("insert"), "1.4")
        self.assertEqual(self.selection(), ())
        self.assert_single_edit("body", "b   ody")

    def test_selected_tab_suppresses_text_class_selection_replacement(self):
        selection = ("1.1", "1.4")
        plain = self.ordinary_text("alpha", "1.4", selection)
        self.key("<Tab>", plain)
        self.assertEqual(plain.get("1.0", "end-1c"), "a\ta")

        self.load("alpha", "1.4", selection)
        self.key("<Tab>")
        self.assertEqual(self.editor.index("insert"), "1.8")
        self.assert_selected_lines(1, 1)
        self.assert_single_edit("alpha", "    alpha")

    def test_tab_in_body_uses_next_four_column_stop(self):
        body = "abcdefghij"
        for column in range(len(body) + 1):
            with self.subTest(column=column):
                self.load(body, f"1.{column}")
                self.key("<Tab>")
                count = 4 - column % 4
                expected = body[:column] + " " * count + body[column:]
                self.assertEqual(self.editor.index("insert"), f"1.{column + count}")
                self.assertEqual(self.selection(), ())
                self.assert_single_edit(body, expected)

    def test_tab_inside_space_indentation_keeps_remaining_prefix_and_body(self):
        original = "      body\n\tuntouched"
        for column in range(7):
            with self.subTest(column=column):
                self.load(original, f"1.{column}")
                self.key("<Tab>")
                count = 4 - column % 4
                self.assertEqual(self.editor.index("insert"), f"1.{column + count}")
                self.assert_single_edit(original, " " * (6 + count) + "body\n\tuntouched")

    def test_zero_length_selection_uses_the_caret_tab_stop(self):
        self.load("alpha\nbeta", "1.2")
        self.editor.tag_add("sel", "1.2", "1.2")
        self.assertEqual(self.selection(), ())
        self.key("<Tab>")
        self.assertEqual(self.editor.index("insert"), "1.4")
        self.assertEqual(self.selection(), ())
        self.assert_single_edit("alpha\nbeta", "al  pha\nbeta")

    def test_tab_in_leading_tabs_uses_python_eight_column_positions(self):
        cases = [
            ("\t", 0, 12, 4),
            ("\t", 1, 12, 12),
            (" \t ", 1, 12, 4),
            (" \t ", 2, 13, 12),
            (" \t ", 3, 12, 12),
            ("\t  ", 2, 13, 12),
        ]
        for prefix, column, new_width, new_column in cases:
            with self.subTest(prefix=repr(prefix), column=column):
                original = prefix + 'body = "a\tb"\n\tuntouched'
                self.load(original, f"1.{column}")
                self.key("<Tab>")
                self.assertEqual(self.editor.index("insert"), f"1.{new_column}")
                self.assert_single_edit(
                    original, " " * new_width + 'body = "a\tb"\n\tuntouched'
                )

    def test_tab_in_body_normalizes_only_the_current_leading_prefix(self):
        original = '\tfoo\tbar = "a\tb"\n \tuntouched = "x\ty"'
        self.load(original, "1.5")
        self.key("<Tab>")
        self.assertEqual(self.editor.index("insert"), "1.16")
        self.assert_single_edit(
            original, '        foo\t    bar = "a\tb"\n \tuntouched = "x\ty"'
        )

    def test_tab_inside_string_keeps_nonleading_tabs_and_uses_visual_column(self):
        original = 'message = "a\tb"\n\tuntouched'
        column = original.index("b")
        self.load(original, f"1.{column}")
        self.key("<Tab>")
        self.assertEqual(self.editor.index("insert"), f"1.{column + 4}")
        self.assert_single_edit(
            original, original[:column] + "    " + original[column:]
        )

    def test_tab_handles_empty_code_whitespace_and_final_empty_lines(self):
        cases = [
            ("", "1.0", "    ", "1.4"),
            ("    ", "1.4", "        ", "1.8"),
            ("body\n", "end-1c", "body\n    ", "2.4"),
            ("body\n\n", "3.0", "body\n\n    ", "3.4"),
        ]
        for original, caret, expected, new_caret in cases:
            with self.subTest(original=repr(original), caret=caret):
                self.load(original, caret)
                self.key("<Tab>")
                self.assertEqual(self.editor.index("insert"), new_caret)
                self.assert_single_edit(original, expected)

    def test_selected_tab_indents_exactly_the_touched_lines(self):
        cases = [
            ("alpha", ("1.1", "1.3"), "    alpha", (1, 1)),
            ("alpha\nbeta\ngamma", ("1.2", "2.2"), "    alpha\n    beta\ngamma", (1, 2)),
            ("alpha\nbeta", ("1.2", "2.0"), "    alpha\nbeta", (1, 1)),
            ("alpha\nbeta", ("1.end", "2.0"), "    alpha\nbeta", (1, 1)),
            ("alpha\nbeta", ("2.0", "2.1"), "alpha\n    beta", (2, 2)),
            ("alpha\nbeta", ("1.0", "end"), "    alpha\n    beta", (1, 2)),
            ("alpha\nbeta", ("1.2", "end-1c"), "    alpha\n    beta", (1, 2)),
            ("alpha\n", ("1.2", "2.0"), "    alpha\n", (1, 1)),
            ("alpha\n", ("1.2", "end"), "    alpha\n    ", (1, 2)),
            ("alpha\n\nbeta", ("1.2", "3.1"), "    alpha\n    \n    beta", (1, 3)),
            ("", ("1.0", "end"), "    ", (1, 1)),
            ("alpha\n", ("2.0", "end"), "alpha\n    ", (2, 2)),
        ]
        for original, selection, expected, lines in cases:
            with self.subTest(original=repr(original), selection=selection):
                self.load(original, selection[0], selection)
                self.key("<Tab>")
                self.assert_selected_lines(*lines)
                self.assert_single_edit(original, expected)

    def test_selected_tab_adds_four_spaces_not_just_the_next_stop(self):
        original = " a\n  b\n   c\n    d"
        expected = "     a\n      b\n       c\n        d"
        self.load(original, "4.end", ("1.0", "end"))
        self.key("<Tab>")
        self.assert_selected_lines(1, 4)
        self.assert_single_edit(original, expected)

    def test_selected_edits_normalize_touched_leading_tabs_only(self):
        prefixes = [
            ("\t", 8),
            (" \t", 8),
            ("\t ", 9),
            ("   \t  ", 10),
            ("\t \t", 16),
            ("        \t", 16),
            ("\t\t", 16),
        ]
        body = 'value = "a\tb"; escaped = "\\t"\t# body tab'
        for sequence, change in [("<Tab>", 4), ("<Shift-Tab>", -4), ("<ISO_Left_Tab>", -4)]:
            for prefix, width in prefixes:
                with self.subTest(key=sequence, prefix=repr(prefix)):
                    original = "\tuntouched\n" + prefix + body + "\n \talso_untouched"
                    expected = "\tuntouched\n" + " " * (width + change) + body + "\n \talso_untouched"
                    self.load(original, "2.end", ("2.1", "3.0"))
                    self.key(sequence)
                    self.assert_selected_lines(2, 2)
                    self.assertEqual(
                        self.editor.index("insert"), f"2.{width + change + len(body)}"
                    )
                    self.assert_single_edit(original, expected)

    def test_selection_caret_in_body_tracks_both_forward_and_reverse_selections(self):
        original = "    alpha\n        beta\n  untouched"
        cases = [("1.6", "1.10", "1.2"), ("2.10", "2.14", "2.6")]
        for caret, indented_caret, outdented_caret in cases:
            for sequence in ("<Tab>", "<Shift-Tab>", "<ISO_Left_Tab>"):
                with self.subTest(caret=caret, key=sequence):
                    self.load(original, caret, ("1.6", "2.10"))
                    self.key(sequence)
                    self.assert_selected_lines(1, 2)
                    expected_caret = indented_caret if sequence == "<Tab>" else outdented_caret
                    self.assertEqual(self.editor.index("insert"), expected_caret)
                    expected = (
                        "        alpha\n            beta\n  untouched"
                        if sequence == "<Tab>" else "alpha\n    beta\n  untouched"
                    )
                    self.assert_single_edit(original, expected)

    def test_repeated_indent_outdent_preserves_selection_and_separate_history(self):
        original = "\talpha\n  beta\nlast"
        self.load(original, "2.3", ("1.2", "2.3"))
        snapshots = [original]
        operations = [
            ("<Tab>", 12, 6, "2.7"),
            ("<Tab>", 16, 10, "2.11"),
            ("<Shift-Tab>", 12, 6, "2.7"),
            ("<Shift-Tab>", 8, 2, "2.3"),
        ]
        for sequence, first_width, second_width, caret in operations:
            with self.subTest(key=sequence, first_width=first_width):
                self.key(sequence)
                expected = " " * first_width + "alpha\n" + " " * second_width + "beta\nlast"
                self.assertEqual(self.text(), expected)
                self.assert_selected_lines(1, 2)
                self.assertEqual(self.editor.index("insert"), caret)
                snapshots.append(expected)
        self.assert_history(snapshots)

    def test_shift_tab_in_body_removes_at_most_four_indentation_columns(self):
        prefixes = [(" " * width, width) for width in range(10)]
        prefixes += [("\t", 8), (" \t ", 9), ("\t \t", 16)]
        for prefix, width in prefixes:
            with self.subTest(prefix=repr(prefix)):
                body = 'value\t= "a\tb"'
                original = "\tuntouched\n" + prefix + body + "\n \talso_untouched"
                self.load(original, f"2.{len(prefix) + 3}")
                self.key("<Shift-Tab>")
                remaining = max(0, width - 4)
                expected = "\tuntouched\n" + " " * remaining + body + "\n \talso_untouched"
                self.assertEqual(self.text(), expected)
                self.assertEqual(self.editor.index("insert"), f"2.{remaining + 3}")
                self.assertEqual(self.selection(), ())
                if original == expected:
                    self.assertFalse(self.editor.edit_modified())
                    self.assert_no_history()
                else:
                    self.assert_single_edit(original, expected)

    def test_iso_left_tab_outdents_the_current_line(self):
        original = "\talpha\n  untouched"
        self.load(original, "1.3")
        self.key("<ISO_Left_Tab>")
        self.assertEqual(self.editor.index("insert"), "1.6")
        self.assertEqual(self.selection(), ())
        self.assert_single_edit(original, "    alpha\n  untouched")

    def test_selected_outdent_handles_short_blank_and_unindented_lines(self):
        original = " \n  one\n   two\n    three\n      four\nno_indent\n\tfive\n \tsix"
        expected = "\none\ntwo\nthree\n  four\nno_indent\n    five\n    six"
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            with self.subTest(key=sequence):
                self.load(original, "8.end", ("1.0", "end"))
                self.key(sequence)
                self.assert_selected_lines(1, 8)
                self.assert_single_edit(original, expected)

    def test_selected_outdent_excludes_an_end_at_next_line_column_zero(self):
        original = "    alpha\n        beta\n  untouched"
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            for selection in (("1.2", "2.0"), ("1.end", "2.0")):
                with self.subTest(key=sequence, selection=selection):
                    self.load(original, "1.end", selection)
                    self.key(sequence)
                    self.assert_selected_lines(1, 1)
                    self.assertEqual(self.editor.index("insert"), "1.5")
                    self.assert_single_edit(original, "alpha\n        beta\n  untouched")

    def test_outdent_handles_empty_code_and_final_lines(self):
        cases = [
            ("", "1.0", "", "1.0"),
            ("body\n", "2.0", "body\n", "2.0"),
            ("body\n   ", "2.3", "body\n", "2.0"),
            ("body\n\t", "2.1", "body\n    ", "2.4"),
        ]
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            for original, caret, expected, new_caret in cases:
                with self.subTest(key=sequence, original=repr(original)):
                    self.load(original, caret)
                    self.key(sequence)
                    self.assertEqual(self.text(), expected)
                    self.assertEqual(self.editor.index("insert"), new_caret)
                    if original == expected:
                        self.assertFalse(self.editor.edit_modified())
                        self.assert_no_history()
                    else:
                        self.assert_single_edit(original, expected)

    def test_outdent_keeps_caret_at_its_logical_position_inside_indentation(self):
        # Removing the first four columns must not jump the caret to the body.
        cases = [
            ("        ", 0, 0),
            ("        ", 2, 0),
            ("        ", 6, 2),
            ("        ", 8, 4),
            (" \t ", 1, 0),
            (" \t ", 2, 4),
            (" \t ", 3, 5),
        ]
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            for prefix, column, expected_column in cases:
                with self.subTest(key=sequence, prefix=repr(prefix), column=column):
                    original = prefix + "body"
                    self.load(original, f"1.{column}")
                    self.key(sequence)
                    width = 4 if prefix == "        " else 5
                    self.assertEqual(self.text(), " " * width + "body")
                    self.assertEqual(self.editor.index("insert"), f"1.{expected_column}")

    def test_noindent_outdent_is_a_safe_noop_with_or_without_selection(self):
        original = 'value = "a\tb"\nother\t= 2'
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            for selection in (None, ("1.3", "2.0"), ("1.1", "end")):
                with self.subTest(key=sequence, selection=selection):
                    self.load(original, "1.5", selection)
                    ranges = self.selection()
                    self.key(sequence)
                    self.assertEqual(self.text(), original)
                    self.assertEqual(self.editor.index("insert"), "1.5")
                    self.assertEqual(self.selection(), ranges)
                    self.assertFalse(self.editor.edit_modified())
                    self.assert_no_history()

    def test_noindent_outdent_does_not_destroy_redo_history(self):
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            for selected in (False, True):
                with self.subTest(key=sequence, selected=selected):
                    self.load("body", "1.end")
                    self.key("<KeyPress-x>")
                    self.assertEqual(self.text(), "bodyx")
                    self.editor.edit_undo()
                    self.assertEqual(self.text(), "body")
                    if selected:
                        self.editor.tag_add("sel", "1.0", "end")
                    self.key(sequence)
                    self.assertEqual(self.text(), "body")
                    self.editor.edit_redo()
                    self.assertEqual(self.text(), "bodyx")

    def test_disabled_editor_does_not_mutate_for_any_indentation_key(self):
        original = '\talpha = "x\ty"\n  beta'
        for sequence in ("<Tab>", "<Shift-Tab>", "<ISO_Left_Tab>"):
            for selection in (None, ("1.2", "2.2")):
                with self.subTest(key=sequence, selection=selection):
                    self.load(original, "1.3", selection)
                    ranges = self.selection()
                    self.editor.configure(state="disabled")
                    self.key(sequence)
                    self.assertEqual(self.text(), original)
                    self.assertEqual(self.editor.index("insert"), "1.3")
                    self.assertEqual(self.selection(), ranges)
                    self.assertEqual(str(self.editor.cget("state")), "disabled")
                    self.assertFalse(self.editor.edit_modified())
                    self.editor.configure(state="normal")
                    self.assert_no_history()

    def test_indentation_keys_keep_focus_in_the_editor(self):
        for sequence in ("<Tab>", "<Shift-Tab>", "<ISO_Left_Tab>"):
            with self.subTest(key=sequence):
                self.load("    body", "1.end")
                self.key(sequence)
                self.assertEqual(self.root.focus_get(), self.editor)

    def assert_focus_traversal(self, sequence, target):
        original = '\talpha = "a\tb"\n    beta'
        self.load(original, "2.6", ("1.2", "2.6"))
        ranges = self.selection()
        self.key(sequence)
        self.assertEqual(self.root.focus_get(), target)
        self.assertEqual(self.text(), original)
        self.assertEqual(self.editor.index("insert"), "2.6")
        self.assertEqual(self.selection(), ranges)
        self.assertFalse(self.editor.edit_modified())
        self.assert_no_history()
        self.assertEqual(self.before.get(), "")
        self.assertEqual(self.after.get(), "")

    def test_control_tab_moves_focus_to_next_control_without_editing(self):
        self.assert_focus_traversal("<Control-Tab>", self.after)

    def test_control_shift_tab_moves_focus_to_previous_control_without_editing(self):
        self.assert_focus_traversal("<Control-Shift-Tab>", self.before)

    def test_control_iso_left_tab_moves_focus_to_previous_control_without_editing(self):
        self.assert_focus_traversal("<Control-ISO_Left_Tab>", self.before)

    def test_each_operation_is_separate_from_surrounding_typing(self):
        cases = [
            ("<Tab>", "body", "bodyx", "bodyx   ", "bodyx   y"),
            ("<Shift-Tab>", "    body", "    bodyx", "bodyx", "bodyxy"),
            ("<ISO_Left_Tab>", "    body", "    bodyx", "bodyx", "bodyxy"),
        ]
        for auto in (True, False):
            for sequence, original, typed, changed, final in cases:
                with self.subTest(autoseparators=auto, key=sequence):
                    self.load(original, "1.end")
                    self.editor.configure(autoseparators=auto)
                    self.key("<KeyPress-x>")
                    self.assertEqual(self.text(), typed)
                    self.key(sequence)
                    self.assertEqual(self.text(), changed)
                    self.assertEqual(
                        self.editor.tk.getboolean(self.editor.cget("autoseparators")), auto
                    )
                    self.key("<KeyPress-y>")
                    self.assertEqual(self.text(), final)
                    self.assert_history([original, typed, changed, final])


if __name__ == "__main__":
    unittest.main()
