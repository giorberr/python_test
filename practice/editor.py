"""Python editor with lexical coloring, line numbers and space-based indentation."""

import builtins
import keyword
import re
from contextlib import contextmanager
from tkinter import Canvas
from tkinter.scrolledtext import ScrolledText

from .theme import DARK_COLORS

INDENT_WIDTH = 4
_HIGHLIGHT_DELAY = 100
_SYNTAX_TAGS = tuple(f"syntax_{name}" for name in (
    "keyword", "string", "number", "comment", "builtin", "definition",
))
_BUILTINS = frozenset(dir(builtins))
_DIGITS = r"[0-9](?:_?[0-9])*"
_STRING_OPEN = re.compile(
    r"(?i:br|rb|fr|rf|tr|rt|r|u|b|f|t)?(?P<quote>'''|\"\"\"|'|\")"
)
_CLOSING_BRACKETS = {"(": ")", "[": "]", "{": "}"}
# Match only string openings: interpolated strings need nested boundary tracking.
# No parser/tokenize pass is required, so bad indentation cannot stop coloring.
_TOKENS = re.compile(
    r"(?P<comment>\#[^\n]*)|(?P<string>" + _STRING_OPEN.pattern + r")"
    r"|(?P<number>0[xX](?:_?[0-9a-fA-F])+|0[oO](?:_?[0-7])+"
    r"|0[bB](?:_?[01])+|(?:" + _DIGITS + r"(?:\.(?:" + _DIGITS + r")?)?"
    r"|\." + _DIGITS + r")(?:[eE][+-]?" + _DIGITS + r")?[jJ]?)"
    r"|(?P<other>\S)"
)


def _string_end(source, opening):
    """Find a tolerant f/t/plain string boundary, without recursive parsing."""
    contexts = []

    def push_string(match):
        prefix = match.group().lower()
        kind = "interpolated" if "f" in prefix or "t" in prefix else "string"
        contexts.append((kind, match.group("quote")))
        return match.end()

    position = push_string(opening)
    while position < len(source):
        kind, closing = contexts[-1]
        char = source[position]
        if kind in ("string", "interpolated"):
            if source.startswith(closing, position):
                position += len(closing)
                contexts.pop()
            elif char == "\n" and len(closing) == 1:
                # Recover an unfinished ordinary short string at its newline.
                contexts.pop()
            elif char == "\\":
                # Backslashes escape quotes, but not f/t replacement braces.
                position += 1
                if position < len(source) and not (
                    kind == "interpolated" and source[position] in "{}"
                ):
                    position += 1
            elif kind == "interpolated" and char == "{":
                if source.startswith("{{", position):
                    position += 2
                else:
                    contexts.append(("field", "}"))
                    position += 1
            else:
                position += 1
        elif kind == "format":
            if char == "{":
                contexts.append(("field", "}"))
            elif char == "}":
                contexts.pop()
            position += 1
        else:  # Replacement expression, or a bracketed part of one.
            nested = _STRING_OPEN.match(source, position)
            if char == "#":
                newline = source.find("\n", position)
                position = len(source) if newline < 0 else newline
            elif nested is not None:
                position = push_string(nested)
            elif char in _CLOSING_BRACKETS:
                contexts.append(("bracket", _CLOSING_BRACKETS[char]))
                position += 1
            elif char == closing:
                contexts.pop()
                position += 1
            elif kind == "field" and char == ":":
                contexts[-1] = ("format", "}")
                position += 1
            else:
                position += 1
        if not contexts:
            return position
    return position


def _syntax_spans(source):
    """Yield tag names and Python string offsets, without requiring valid code."""
    definition = False
    previous = None
    position = 0
    while position < len(source):
        match = _TOKENS.match(source, position)
        if match is None:  # Whitespace does not change definition/name context.
            position += 1
            continue
        category = match.lastgroup
        end = match.end()
        if category == "string":
            end = _string_end(source, match)
        elif category == "other" and source[position].isidentifier():
            category = "name"
            # XID_Continue includes combining marks and characters absent from
            # regex \w. Do not normalize: spans must index the original source.
            while end < len(source) and ("a" + source[end]).isidentifier():
                end += 1
        word = source[position:end]
        if category == "name":
            if keyword.iskeyword(word):
                category = "keyword"
            elif definition:
                category = "definition"
            elif word in _BUILTINS and previous != ".":
                category = "builtin"
        if category not in ("name", "other"):
            yield f"syntax_{category}", position, end
        definition = category == "keyword" and word in ("def", "class")
        previous = word
        position = end


class CodeEditor(ScrolledText):
    _w: str  # Native Text path, omitted by some tkinter type stubs.

    def __init__(self, master=None, *, scale=1.0, **kwargs):
        kwargs.setdefault("undo", True)
        super().__init__(master, **kwargs)
        self._destroyed = False
        self._highlight_after = None
        self._gutter_after = None
        self._gutter_padding = max(1, round(8 * scale))
        # Tk 8.6 indexes non-BMP characters as two units; Tk 9 uses one.
        self._utf16_columns = self.tk.call("string", "length", "\U0001f600") == 2
        for tag in _SYNTAX_TAGS:
            self.tag_configure(
                tag, foreground=DARK_COLORS.get(tag, DARK_COLORS["foreground"])
            )
        self.tag_raise("sel")
        # Let the Text widget, not Canvas's default physical size, request height.
        self.gutter = Canvas(
            self.frame, width=1, height=1, background=DARK_COLORS["background"],
            highlightthickness=0, borderwidth=0, takefocus=False,
        )
        # ScrolledText.__str__ names the frame, not the actual Text window.
        self.tk.call(
            "pack", str(self.gutter), "-side", "left", "-fill", "y", "-before", self._w
        )
        self._observe_text_commands()
        for event in ("<Configure>", "<Map>", "<Expose>", "<<WidgetViewSync>>"):
            self.bind(event, self._schedule_gutter, add="+")
        self.gutter.bind("<Configure>", self._schedule_gutter)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.bind("<Tab>", self.indent)
        self.bind("<Shift-Tab>", self.outdent)
        self.bind("<ISO_Left_Tab>", self.outdent)
        self.bind("<Control-Tab>", self.focus_next)
        self.bind("<Control-Shift-Tab>", self.focus_previous)
        self.bind("<Control-ISO_Left_Tab>", self.focus_previous)
        self._schedule_highlight()
        self._schedule_gutter()

    def _observe_text_commands(self):
        # Forward in Tcl to preserve native results, errors and variable scope.
        # Observing commands also catches class bindings and programmatic edits,
        # without owning <<Modified>> or the app's replaceable yscrollcommand.
        self._native_command = self._w + "_editor_native"
        self._observer_command = self.register(self._on_text_command)
        self.tk.call("rename", self._w, self._native_command)
        body = self.tk.call(
            "format",
            "set result [uplevel 1 [linsert $args 0 %s]]\n%s {*}$args\nreturn $result",
            (self._native_command,), (self._observer_command,),
        )
        self.tk.call("proc", self._w, "args", body)

    def _on_text_command(self, *args):
        command = args[0]
        changed = command in ("insert", "delete", "replace") or (
            command == "edit" and args[1:2] in (("undo",), ("redo",))
        )
        if changed:
            self._schedule_highlight()
        if changed or (
            command in ("yview", "xview", "see", "scan") and len(args) > 1
        ) or (command == "configure" and len(args) > 2) or (
            command == "tag" and args[1:2] in (
                ("add",), ("remove",), ("delete",), ("configure",),
                ("raise",), ("lower",),
            )
        ):
            self._schedule_gutter()

    def _schedule_highlight(self):
        if self._destroyed:
            return
        if self._highlight_after is not None:
            self.after_cancel(self._highlight_after)
        self._highlight_after = self.after(_HIGHLIGHT_DELAY, self._highlight)

    def _highlight(self):
        self._highlight_after = None
        source = self.get("1.0", "end-1c")
        ranges = {tag: [] for tag in _SYNTAX_TAGS}
        offset, line, column = 0, 1, 0

        def index(end):
            nonlocal offset, line, column
            fragment = source[offset:end]
            newlines = fragment.count("\n")
            if newlines:
                line += newlines
                column = 0
                fragment = fragment.rsplit("\n", 1)[-1]
            column += (
                len(fragment.encode("utf-16-le", "surrogatepass")) // 2
                if self._utf16_columns else len(fragment)
            )
            offset = end
            return f"{line}.{column}"

        for tag, start, end in _syntax_spans(source):
            ranges[tag].extend((index(start), index(end)))
        for tag, indices in ranges.items():
            self.tag_remove(tag, "1.0", "end")
            if indices:
                self.tag_add(tag, *indices)

    def _schedule_gutter(self, event=None):
        if not self._destroyed and self._gutter_after is None:
            self._gutter_after = self.after_idle(self._redraw_gutter)

    def _redraw_gutter(self):
        self._gutter_after = None
        font = self.cget("font")
        digits = len(self.index("end-1c").split(".")[0])
        digit_width = max(
            int(self.tk.call("font", "measure", font, digit))
            for digit in "0123456789"
        )
        width = digits * digit_width + 2 * self._gutter_padding
        if int(self.gutter.cget("width")) != width:
            self.gutter.configure(width=width)
        self.gutter.delete("all")
        ascent = int(self.tk.call("font", "metrics", font, "-ascent"))
        offset_y = self.winfo_rooty() - self.gutter.winfo_rooty()
        index = self.index("@0,0")
        previous_line = None
        while True:
            info = self.dlineinfo(index)
            if info is None:
                break
            line = index.split(".")[0]
            if line != previous_line:
                self.gutter.create_text(
                    width - self._gutter_padding,
                    offset_y + info[1] + info[4] - ascent,
                    anchor="ne", text=line, font=font, fill=DARK_COLORS["muted"],
                )
                previous_line = line
            next_index = self.index(f"{index} +1 display lines display linestart")
            if self.compare(next_index, "<=", index):
                break
            index = next_index

    def _on_destroy(self, event):
        if event.widget is not self or self._destroyed:
            return
        self._destroyed = True
        for attribute in ("_highlight_after", "_gutter_after"):
            pending = getattr(self, attribute)
            if pending is not None:
                self.after_cancel(pending)
                setattr(self, attribute, None)
        self.tk.call("rename", self._w, "")
        self.deletecommand(self._observer_command)
        self.gutter.destroy()

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
