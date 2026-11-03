"""Code-entry widget with explicit, space-based indentation bindings."""

from contextlib import contextmanager
from tkinter.scrolledtext import ScrolledText

INDENT_WIDTH = 4


class CodeEditor(ScrolledText):
    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("undo", True)
        super().__init__(master, **kwargs)
        self.bind("<Tab>", self.indent)
        self.bind("<Shift-Tab>", self.outdent)
        self.bind("<ISO_Left_Tab>", self.outdent)
        self.bind("<Control-Tab>", self.focus_next)
        self.bind("<Control-Shift-Tab>", self.focus_previous)
        self.bind("<Control-ISO_Left_Tab>", self.focus_previous)

    @contextmanager
    def _edit_group(self):
        auto = self.cget("autoseparators")
        self.edit_separator()
        self.configure(autoseparators=False)
        try:
            yield
        finally:
            self.edit_separator()
            self.configure(autoseparators=auto)

    def _selected_lines(self):
        selection = self.tag_ranges("sel")
        if not selection:
            line = int(self.index("insert").split(".")[0])
            return line, line, False
        first = int(self.index(selection[0]).split(".")[0])
        last, column = map(int, self.index(selection[1]).split("."))
        # An exclusive selection end at column zero belongs to the previous line.
        if column == 0 and last > first:
            last -= 1
        return first, last, True

    def _leading_whitespace(self, line):
        text = self.get(f"{line}.0", f"{line}.end")
        return text[:len(text) - len(text.lstrip(" \t"))]

    def _replace_prefix(self, line, old, new):
        if old != new:
            caret_line, caret_column = map(int, self.index("insert").split("."))
            target_column = None
            if caret_line == line and caret_column <= len(old):
                before = len(old[:caret_column].expandtabs(8))
                delta = len(new) - len(old.expandtabs(8))
                target_column = max(0, before + delta)
            self.delete(f"{line}.0", f"{line}.{len(old)}")
            self.insert(f"{line}.0", new)
            if target_column is not None:
                self.mark_set("insert", f"{line}.{target_column}")

    def _change_lines(self, direction):
        first, last, selected = self._selected_lines()
        changes = []
        for line in range(first, last + 1):
            old = self._leading_whitespace(line)
            # Python interprets legacy indentation tabs at eight-column stops.
            width = len(old.expandtabs(8))
            new = " " * max(0, width + direction * INDENT_WIDTH)
            if old != new:
                changes.append((line, old, new))
        if changes:
            with self._edit_group():
                for line, old, new in changes:
                    self._replace_prefix(line, old, new)
            if selected:
                self.tag_remove("sel", "1.0", "end")
                self.tag_add("sel", f"{first}.0", f"{last + 1}.0")
            self.see("insert")

    def indent(self, event=None):
        if self.cget("state") != "normal":
            return None
        if self.tag_ranges("sel"):
            self._change_lines(1)
        else:
            line, column = map(int, self.index("insert").split("."))
            old = self._leading_whitespace(line)
            before = self.get(f"{line}.0", "insert")
            width = len(before.expandtabs(8))
            spaces = " " * (INDENT_WIDTH - width % INDENT_WIDTH)
            with self._edit_group():
                if column <= len(old):
                    normalized = old.expandtabs(8)
                    self._replace_prefix(line, old, normalized[:width] + spaces + normalized[width:])
                    self.mark_set("insert", f"{line}.{width + len(spaces)}")
                else:
                    self._replace_prefix(line, old, old.expandtabs(8))
                    self.insert("insert", spaces)
            self.see("insert")
        return "break"

    def outdent(self, event=None):
        if self.cget("state") != "normal":
            return None
        self._change_lines(-1)
        return "break"

    def focus_next(self, event=None):
        target = self.tk_focusNext()
        if target is not None:
            target.focus_set()
        return "break"

    def focus_previous(self, event=None):
        target = self.tk_focusPrev()
        if target is not None:
            target.focus_set()
        return "break"
