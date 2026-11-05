"""Lexical coloring and real-Tk editor display regressions, without app data."""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import patch

from practice.editor import CodeEditor, _HIGHLIGHT_DELAY, _syntax_spans
from practice.theme import DARK_COLORS


class SyntaxSpanTests(unittest.TestCase):
    def spans(self, source):
        return [(tag, source[start:end]) for tag, start, end in _syntax_spans(source)]

    def test_categories_and_definition_names(self):
        self.assertEqual(self.spans(
            'class Example:\n    async def work(self):\n'
            '        return print(42, "hello") # note\n'
        ), [
            ("syntax_keyword", "class"), ("syntax_definition", "Example"),
            ("syntax_keyword", "async"), ("syntax_keyword", "def"),
            ("syntax_definition", "work"), ("syntax_keyword", "return"),
            ("syntax_builtin", "print"), ("syntax_number", "42"),
            ("syntax_string", '"hello"'), ("syntax_comment", "# note"),
        ])

    def test_comments_and_strings_do_not_leak_keywords_or_builtins(self):
        literals = [
            "'if True: print(42) # not a comment'",
            'r"class False # len(2)"',
            "'''def name():\n    return int(3) # literal\n'''",
            '"""while True:\n    pass # literal"""',
            'f"return {len(values)}"',
            '"escaped \\\" quote; if True"',
        ]
        for literal in literals:
            with self.subTest(literal=literal):
                self.assertEqual(self.spans(literal), [("syntax_string", literal)])
        comment = '# def name(): return "string", print(123)'
        self.assertEqual(self.spans(comment), [("syntax_comment", comment)])

    def test_unfinished_strings_and_statements(self):
        for literal in ("'if True # print(1)", '"return len(',
                        "'''class X:\nreturn 42", 'r"""if True:\n# comment',
                        "'trailing\\", "'''trailing\\"):
            with self.subTest(literal=literal):
                self.assertEqual(self.spans(literal), [("syntax_string", literal)])
        self.assertEqual(self.spans("def unfinished(\n    value=42,"), [
            ("syntax_keyword", "def"), ("syntax_definition", "unfinished"),
            ("syntax_number", "42"),
        ])
        self.assertEqual(self.spans("'unfinished\nreturn 1"), [
            ("syntax_string", "'unfinished"), ("syntax_keyword", "return"),
            ("syntax_number", "1"),
        ])
        continued = "'escaped\\\nif True'"
        self.assertEqual(self.spans(continued), [("syntax_string", continued)])

    def test_bad_indentation_does_not_stop_later_coloring(self):
        source = "if True:\n    pass\n  return len([1])\n\t def later(:\nprint(2)"
        spans = self.spans(source)
        self.assertIn(("syntax_keyword", "return"), spans)
        self.assertIn(("syntax_definition", "later"), spans)
        self.assertIn(("syntax_builtin", "print"), spans)
        self.assertEqual(spans[-1], ("syntax_number", "2"))

    def test_numeric_literals_and_name_boundaries(self):
        numbers = "0 123 1_000 0x_FF 0b_101 0o_77 .5 1. 1.25 2e-3 4.5E+6 2j"
        self.assertEqual(self.spans(numbers), [
            ("syntax_number", number) for number in numbers.split()
        ])
        self.assertEqual(self.spans("sprint = value2; obj.print(); def len(): pass"), [
            ("syntax_keyword", "def"), ("syntax_definition", "len"),
            ("syntax_keyword", "pass"),
        ])

    def test_unicode_offsets_are_python_string_offsets(self):
        source = '变量 = "😀"; print(42)\ndef 𝛂(): return "🚀"'
        spans = list(_syntax_spans(source))
        for tag, start, end in spans:
            self.assertGreater(end, start)
            if tag == "syntax_builtin":
                self.assertEqual(start, source.index("print"))
                self.assertEqual(source[start:end], "print")
        self.assertIn(("syntax_definition", "𝛂"), self.spans(source))

    def test_interpolated_fields_can_reuse_the_outer_quotes(self):
        for prefix in ("f", "F", "fr", "rf", "t", "T", "tr", "rt"):
            for quote in ("'", '"', "'''", '"""'):
                literal = prefix + quote + "{data[" + quote + "#" + quote + "]}" + quote
                with self.subTest(literal=literal):
                    self.assertEqual(self.spans("x = " + literal + "; print(42) # real"), [
                        ("syntax_string", literal), ("syntax_builtin", "print"),
                        ("syntax_number", "42"), ("syntax_comment", "# real"),
                    ])

    def test_interpolated_strings_track_nested_fields_strings_and_format_specs(self):
        literals = [
            'f"{f"{data["#"]}"}"',
            't"{t"{data["#"]}"}"',
            'f"{ {"#": data["#"]}["#"] }"',
            'f"{(value := data["#"])}"',
            'f"{data["#"]!r:>{width}.{precision}}"',
            'f"{value:">10}"',
            'f"{{literal}} {data["#"]} {{print(99)}}"',
            'f"{value:{data["#"]}}"',
            r'f"\{data["#"]}"',
            r'f"{{\"#\"}} {data["#"]}"',
        ]
        for literal in literals:
            with self.subTest(literal=literal):
                self.assertEqual(self.spans(literal + "; print(42)"), [
                    ("syntax_string", literal), ("syntax_builtin", "print"),
                    ("syntax_number", "42"),
                ])

    def test_comments_inside_replacement_fields_do_not_end_the_string(self):
        for prefix in ("f", "t"):
            literal = prefix + '"{data[  # "quoted" comment\n    "#"]}"'
            with self.subTest(prefix=prefix):
                self.assertEqual(self.spans(literal + "; print(42)"), [
                    ("syntax_string", literal), ("syntax_builtin", "print"),
                    ("syntax_number", "42"),
                ])

    def test_interpolation_scanning_tolerates_bad_indent_and_unfinished_input(self):
        literal = 'f"{data["#"]}"'
        source = "if True:\n    pass\n  x = " + literal + "\nreturn len([1])"
        self.assertEqual(self.spans(source), [
            ("syntax_keyword", "if"), ("syntax_keyword", "True"),
            ("syntax_keyword", "pass"), ("syntax_string", literal),
            ("syntax_keyword", "return"), ("syntax_builtin", "len"),
            ("syntax_number", "1"),
        ])
        for unfinished in ('f"{data["#"]', 't"{data["#"]', 'f"{f"{value',
                           'f"{value:{width', 'f"{value # "comment"', 'f"text\\'):
            with self.subTest(unfinished=unfinished):
                self.assertEqual(self.spans(unfinished), [("syntax_string", unfinished)])

    def test_combining_identifiers_keep_full_names_and_original_offsets(self):
        source = "a\u0301len = 1\ndef a\u0301():\n    return a\u0301len"
        definition_start = source.index("def ") + len("def ")
        self.assertEqual(list(_syntax_spans(source)), [
            ("syntax_number", source.index("1"), source.index("1") + 1),
            ("syntax_keyword", source.index("def"), source.index("def") + 3),
            ("syntax_definition", definition_start, definition_start + len("a\u0301")),
            ("syntax_keyword", source.index("return"), source.index("return") + 6),
        ])
        self.assertEqual(self.spans(source), [
            ("syntax_number", "1"), ("syntax_keyword", "def"),
            ("syntax_definition", "a\u0301"), ("syntax_keyword", "return"),
        ])

    def test_python_identifier_rules_not_regex_word_boundaries(self):
        for name in ("a\u0301len", "a\u00b7len", "\u2118len", "a\u203flen", "a\u0301\u0327len"):
            with self.subTest(name=name):
                self.assertTrue(name.isidentifier())
                source = name + " = 1\ndef " + name + "():\n    return " + name + "\nprint(42)"
                self.assertEqual(self.spans(source), [
                    ("syntax_number", "1"), ("syntax_keyword", "def"),
                    ("syntax_definition", name), ("syntax_keyword", "return"),
                    ("syntax_builtin", "print"), ("syntax_number", "42"),
                ])


class EditorDisplayTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.callback_errors = []
        self.root.report_callback_exception = (
            lambda kind, error, traceback: self.callback_errors.append(str(error))
        )
        # Tcl timer errors do not go through report_callback_exception.
        self.root.tk.createcommand("bgerror", self.callback_errors.append)
        self.addCleanup(self.destroy_root)
        self.root.title("Editor display tests")
        self.root.geometry("640x360+40+40")
        self.editor = CodeEditor(
            self.root, width=60, height=10, wrap="none", font=("Courier", 12),
            exportselection=False, background=DARK_COLORS["surface"],
            foreground=DARK_COLORS["foreground"],
            selectbackground=DARK_COLORS["selection"],
        )
        self.editor.pack(fill="both", expand=True)
        self.root.update()

    def destroy_root(self):
        if self.root.tk.call("info", "commands", "."):
            self.root.destroy()
        self.root.tk.deletecommand("bgerror")
        self.assertEqual(self.callback_errors, [], "Tk display callback failed")

    def settle(self):
        done = tk.BooleanVar(self.root)
        self.root.after(_HIGHLIGHT_DELAY + 30, done.set, True)
        self.root.wait_variable(done)
        self.root.update()
        self.assertEqual(self.callback_errors, [])

    def load(self, source):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", source)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.editor.mark_set("insert", "1.0")
        self.editor.yview_moveto(0)
        self.settle()

    def tagged(self, category):
        ranges = self.editor.tag_ranges(f"syntax_{category}")
        return [self.editor.get(start, end) for start, end in zip(ranges[::2], ranges[1::2])]

    def gutter_items(self):
        return {
            int(self.editor.gutter.itemcget(item, "text")): item
            for item in self.editor.gutter.find_all()
        }

    def assert_gutter_aligned(self):
        editor = self.editor
        items = self.gutter_items()
        total = int(editor.index("end-1c").split(".")[0])
        visible = {
            line: editor.dlineinfo(f"{line}.0") for line in range(1, total + 1)
        }
        visible = {line: info for line, info in visible.items() if info is not None}
        self.assertEqual(set(items), set(visible))
        ascent = int(editor.tk.call("font", "metrics", editor.cget("font"), "-ascent"))
        offset = editor.winfo_rooty() - editor.gutter.winfo_rooty()
        for line, item in items.items():
            with self.subTest(line=line):
                x, y = editor.gutter.coords(item)
                info = visible[line]
                self.assertEqual(y + ascent, offset + info[1] + info[4])
                self.assertLess(x, editor.gutter.winfo_width())
                self.assertEqual(editor.gutter.itemcget(item, "anchor"), "ne")
        self.assertTrue(items)

    def test_gutter_does_not_impose_a_height_on_short_editors(self):
        self.editor.configure(height=2)
        self.root.update_idletasks()
        self.assertEqual(int(self.editor.gutter.cget("height")), 1)
        self.assertEqual(
            self.editor.frame.winfo_reqheight(),
            max(self.editor.winfo_reqheight(), self.editor.vbar.winfo_reqheight()),
        )

    def test_syntax_tags_and_non_bmp_tk_columns(self):
        self.load('变量 = "😀"; print(42) # 💻 class\ndef 𝛂():\n    return "🚀"')
        self.assertEqual(self.tagged("keyword"), ["def", "return"])
        self.assertEqual(self.tagged("definition"), ["𝛂"])
        self.assertEqual(self.tagged("builtin"), ["print"])
        self.assertEqual(self.tagged("number"), ["42"])
        self.assertEqual(self.tagged("comment"), ["# 💻 class"])
        self.assertEqual(self.tagged("string"), ['"😀"', '"🚀"'])
        for category, word in (("builtin", "print"), ("definition", "𝛂")):
            self.assertEqual(
                str(self.editor.tag_ranges(f"syntax_{category}")[0]),
                self.editor.search(word, "1.0", exact=True),
            )
        # The invalid character before a keyword still consumes Tk column units.
        self.load("😀; return len([2])")
        self.assertEqual(self.tagged("keyword"), ["return"])
        self.assertEqual(self.tagged("builtin"), ["len"])
        self.assertEqual(self.tagged("number"), ["2"])

    def test_invalid_indentation_and_unfinished_multiline_string_recover(self):
        self.load("if True:\n    pass\n  return print(3)\ntext = '''def fake():\nreturn 42")
        self.assertEqual(self.tagged("keyword"), ["if", "True", "pass", "return"])
        self.assertEqual(self.tagged("builtin"), ["print"])
        self.assertEqual(self.tagged("string"), ["'''def fake():\nreturn 42"])
        self.editor.insert("end-1c", "'''\nreturn len([])")
        self.settle()
        self.assertEqual(self.tagged("keyword")[-1], "return")
        self.assertEqual(self.tagged("builtin"), ["print", "len"])
        self.assertEqual(self.tagged("string"), ["'''def fake():\nreturn 42'''"])

    def test_theme_colors_selection_priority_and_scale(self):
        colors = {
            "syntax_keyword": "#c6a0f6", "syntax_string": "#a6d189",
            "syntax_number": "#efb080", "syntax_comment": "#8b9bb0",
            "syntax_builtin": "#8ab4f8", "syntax_definition": "#7dcfff",
        }
        with patch.dict(DARK_COLORS, colors):
            scaled = CodeEditor(self.root, scale=2.0, font=self.editor.cget("font"))
        self.addCleanup(scaled.frame.destroy)
        self.root.update()
        for tag, color in colors.items():
            self.assertEqual(scaled.tag_cget(tag, "foreground"), color)
            self.assertLess(scaled.tag_names().index(tag), scaled.tag_names().index("sel"))
        self.assertEqual(scaled.gutter.cget("background"), DARK_COLORS["background"])
        self.assertEqual(
            int(scaled.gutter.cget("width")) - int(self.editor.gutter.cget("width")), 16
        )
        self.assertEqual(str(scaled.gutter.cget("takefocus")), "0")

    def test_native_typing_delete_undo_redo_updates_highlighting(self):
        self.load("cl")
        self.editor.mark_set("insert", "end-1c")
        self.editor.focus_force()
        self.root.update()
        for letter in "ass":
            self.editor.event_generate("<KeyPress>", keysym=letter)
        self.settle()
        self.assertEqual(self.tagged("keyword"), ["class"])
        self.editor.edit_undo()
        self.settle()
        self.assertEqual(self.editor.get("1.0", "end-1c"), "cl")
        self.assertEqual(self.tagged("keyword"), [])
        self.editor.edit_redo()
        self.settle()
        self.assertEqual(self.tagged("keyword"), ["class"])
        self.editor.mark_set("insert", "end-1c")
        self.editor.focus_force()
        self.root.update()
        self.assertEqual(self.root.focus_get(), self.editor)
        self.editor.event_generate("<BackSpace>", when="now")
        self.settle()
        self.assertEqual(self.editor.get("1.0", "end-1c"), "clas")
        self.assertEqual(self.tagged("keyword"), [])

    def test_replace_undo_redo_and_programmatic_exercise_changes(self):
        self.load("return 1")
        self.editor.replace("1.0", "end-1c", "class New:\n    pass")
        self.settle()
        self.assertEqual(self.tagged("definition"), ["New"])
        self.assertEqual(self.tagged("number"), [])
        self.assert_gutter_aligned()
        self.editor.edit_undo()
        self.settle()
        self.assertEqual(self.tagged("keyword"), ["return"])
        self.assertEqual(self.tagged("number"), ["1"])
        self.assert_gutter_aligned()
        self.editor.edit_redo()
        self.settle()
        self.assertEqual(self.tagged("definition"), ["New"])
        self.assert_gutter_aligned()
        self.load("# next exercise\ndef solve():\n    return None\n")
        self.assertEqual(self.tagged("definition"), ["solve"])
        self.assertEqual(self.tagged("number"), [])
        self.assertFalse(self.editor.edit_modified())
        with self.assertRaises(tk.TclError):
            self.editor.edit_undo()
        self.assert_gutter_aligned()

    def test_highlighting_preserves_selection_focus_modified_events_and_redo(self):
        self.load("return len([1])")
        self.editor.insert("end-1c", " # edit")
        self.editor.edit_separator()
        self.editor.edit_undo()
        self.editor.tag_add("sel", "1.0", "1.6")
        self.editor.mark_set("insert", "1.3")
        self.settle()
        modified_events = []
        self.editor.bind("<<Modified>>", lambda event: modified_events.append(True))
        selection = tuple(map(str, self.editor.tag_ranges("sel")))
        for modified in (False, True):
            with self.subTest(modified=modified):
                self.editor.edit_modified(modified)
                self.editor.focus_force()
                self.root.update()
                self.assertEqual(
                    self.root.focus_get(), self.editor,
                    "Editor must own focus before scheduling display callbacks",
                )
                modified_events.clear()
                self.editor._schedule_highlight()
                self.editor._schedule_gutter()
                self.settle()
                self.assertEqual(self.editor.edit_modified(), modified)
                self.assertEqual(modified_events, [])
                self.assertEqual(tuple(map(str, self.editor.tag_ranges("sel"))), selection)
                self.assertEqual(self.editor.index("insert"), "1.3")
                self.assertEqual(self.root.focus_get(), self.editor)
        self.editor.edit_redo()
        self.settle()
        self.assertEqual(self.editor.get("1.0", "end-1c"), "return len([1]) # edit")
        self.editor.edit_undo()
        with self.assertRaises(tk.TclError):
            self.editor.edit_undo()

    def test_highlighting_does_not_split_typing_history(self):
        for auto in (False, True):
            with self.subTest(autoseparators=auto):
                self.load("")
                self.editor.configure(autoseparators=auto)
                self.editor.insert("end-1c", "pri")
                self.settle()
                self.editor.insert("end-1c", "nt")
                self.settle()
                self.assertEqual(self.tagged("builtin"), ["print"])
                self.editor.edit_undo()
                self.settle()
                self.assertEqual(self.editor.get("1.0", "end-1c"), "")
                with self.assertRaises(tk.TclError):
                    self.editor.edit_undo()
                self.editor.edit_redo()
                self.settle()
                self.assertEqual(self.tagged("builtin"), ["print"])

    def test_disabled_editor_and_native_results_errors_and_search_count(self):
        self.load("return 1")
        count = tk.IntVar(self.root)
        self.assertEqual(self.editor.search("return", "1.0", count=count), "1.0")
        self.assertEqual(count.get(), 6)
        self.assertEqual(self.editor.count("1.0", "1.end", "chars"), (8,))
        with self.assertRaises(tk.TclError) as native:
            self.editor.tk.call(self.editor._native_command, "edit", "undo")
        with self.assertRaises(tk.TclError) as observed:
            self.editor.edit_undo()
        self.assertEqual(str(observed.exception), str(native.exception))
        self.editor.configure(state="disabled")
        self.editor.insert("1.0", "class ")
        self.editor.delete("1.0", "end")
        self.settle()
        self.assertEqual(self.editor.get("1.0", "end-1c"), "return 1")
        self.assertEqual(self.tagged("keyword"), ["return"])
        self.assertFalse(self.editor.edit_modified())
        self.assertEqual(str(self.editor.cget("state")), "disabled")

    def test_gutter_tracks_scrollbar_replacement_scrolling_and_see(self):
        self.load("\n".join(f"value = {line}" for line in range(300)))
        self.editor.vbar.destroy()
        self.editor.vbar = ttk.Scrollbar(
            self.editor.frame, orient="vertical", command=self.editor.yview, takefocus=False
        )
        self.editor.vbar.pack(side="right", fill="y")
        self.editor.configure(yscrollcommand=self.editor.vbar.set)
        self.root.update()
        self.assert_gutter_aligned()
        self.assertLess(len(self.gutter_items()), 30)
        command = self.editor.tk.splitlist(self.editor.vbar.cget("command"))
        self.editor.tk.call(*command, "moveto", 0.5)
        self.root.update()
        self.assertGreater(min(self.gutter_items()), 100)
        self.assert_gutter_aligned()
        self.assertEqual(tuple(self.editor.vbar.get()), self.editor.yview())
        self.editor.yview_scroll(3, "units")
        self.root.update()
        self.assert_gutter_aligned()
        self.editor.see("290.0")
        self.root.update()
        self.assertIn(290, self.gutter_items())
        self.assert_gutter_aligned()
        self.editor.yview_moveto(0)
        self.root.update()
        before = self.editor.yview()
        self.editor.event_generate("<MouseWheel>", delta=-120, x=30, y=20)
        self.root.update()
        self.assertNotEqual(before, self.editor.yview())
        self.assert_gutter_aligned()

    def test_gutter_resize_font_spacing_and_partial_line_scroll(self):
        self.load("\n".join("print('long line') " * 12 for _ in range(100)))
        self.editor.configure(font=("Courier", 16), spacing1=5, spacing3=4, pady=9)
        self.root.geometry("720x280+40+40")
        self.root.update()
        self.assert_gutter_aligned()
        self.editor.yview_moveto(0.137)
        self.editor.xview_moveto(0.4)
        self.root.update()
        self.assert_gutter_aligned()
        self.root.geometry("560x450+40+40")
        self.root.update()
        self.assert_gutter_aligned()

    def test_wrapping_numbers_each_logical_line_only_once(self):
        self.editor.configure(wrap="word")
        self.load("word " * 70 + "\nreturn 1\n" + "other " * 200)
        items = self.gutter_items()
        self.assertEqual(len(items), len(self.editor.gutter.find_all()))
        self.assert_gutter_aligned()
        self.editor.yview_scroll(1, "units")
        self.root.update()
        first = self.editor.index("@0,0")
        line = int(first.split(".")[0])
        self.assertNotEqual(first, f"{line}.0")
        info = self.editor.dlineinfo(first)
        assert info is not None
        item = self.gutter_items()[line]
        ascent = int(self.editor.tk.call("font", "metrics", self.editor.cget("font"), "-ascent"))
        self.assertEqual(self.editor.gutter.coords(item)[1] + ascent, info[1] + info[4])
        self.assertEqual(len(self.gutter_items()), len(self.editor.gutter.find_all()))

    def test_digit_width_expands_and_shrinks_on_edit_undo_redo(self):
        self.load("\n".join("pass" for _ in range(9)))
        one_digit = int(self.editor.gutter.cget("width"))
        self.editor.insert("end-1c", "\npass")
        self.root.update()
        two_digits = int(self.editor.gutter.cget("width"))
        self.assertGreater(two_digits, one_digit)
        self.assert_gutter_aligned()
        self.editor.edit_undo()
        self.root.update()
        self.assertEqual(int(self.editor.gutter.cget("width")), one_digit)
        self.editor.edit_redo()
        self.root.update()
        self.assertEqual(int(self.editor.gutter.cget("width")), two_digits)
        self.editor.insert("end-1c", "\npass" * 90)
        self.root.update()
        self.assertGreater(int(self.editor.gutter.cget("width")), two_digits)
        self.editor.delete("2.0", "end")
        self.root.update()
        self.assertEqual(int(self.editor.gutter.cget("width")), one_digit)
        self.assert_gutter_aligned()
        self.load("")
        self.assertEqual(set(self.gutter_items()), {1})
        self.assert_gutter_aligned()

    def test_highlighting_is_debounced_and_idle_editor_does_not_poll(self):
        self.load("")
        with patch.object(self.editor, "_highlight", wraps=self.editor._highlight) as highlight:
            for letter in "print(42)":
                self.editor.insert("end-1c", letter)
            self.settle()
            self.assertEqual(highlight.call_count, 1)
            with patch.object(self.editor, "_redraw_gutter", wraps=self.editor._redraw_gutter) as redraw:
                self.settle()
                self.assertEqual(highlight.call_count, 1)
                self.assertEqual(redraw.call_count, 0)
                self.assertIsNone(self.editor._highlight_after)
                self.assertIsNone(self.editor._gutter_after)

    def assert_jobs_removed(self, editor, pending):
        self.assertIsNone(editor._highlight_after)
        self.assertIsNone(editor._gutter_after)
        remaining = self.root.tk.splitlist(self.root.tk.call("after", "info"))
        for identifier in pending:
            self.assertIsNotNone(identifier)
            self.assertNotIn(identifier, remaining)
        for command in (editor._w, editor._native_command, editor._observer_command):
            self.assertFalse(self.root.tk.call("info", "commands", command))

    def test_widget_frame_and_tcl_destruction_cancel_callbacks_and_proxy(self):
        self.settle()
        for mode in ("widget", "frame", "tcl"):
            with self.subTest(mode=mode):
                editor = CodeEditor(self.root)
                editor.insert("1.0", "return 42\n" * 10)
                pending = (editor._highlight_after, editor._gutter_after)
                if mode == "widget":
                    editor.destroy()
                elif mode == "frame":
                    editor.frame.destroy()
                else:
                    editor.tk.call("destroy", editor._w)
                self.assert_jobs_removed(editor, pending)
                self.assertFalse(editor.gutter.winfo_exists())
                self.settle()
                editor.frame.destroy()

    def test_root_destruction_cancels_callbacks(self):
        self.editor.insert("1.0", "return 42")
        pending = (self.editor._highlight_after, self.editor._gutter_after)
        self.root.destroy()
        self.assert_jobs_removed(self.editor, pending)


if __name__ == "__main__":
    unittest.main()
