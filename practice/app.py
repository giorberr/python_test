"""Local algorithm practice desktop app. Run with: python app.py"""

import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from .checker import check
from .display import DisplaySettings, enable_windows_dpi_awareness
from .editor import CodeEditor
from .exercises import EXERCISES
from .progress import ProgressStore
from .theme import apply_dark_theme

DATA_FILE = Path(__file__).resolve().parent.parent / 'data' / 'practice_progress.json'
MOCKS = {
    "Warm-up: Contains Duplicate + Two Sum": (0, 1),
    "Practice set 1: Group Anagrams + Merge Intervals": (6, 9),
    "Practice set 2: Longest Substring + Number of Islands": (7, 13),
    "Practice set 3: Subarray Sum + Coin Change": (11, 14),
}


class PracticeApp:
    def __init__(self, root):
        self.root = root
        root.title("Python Algorithm Practice")
        self.display = DisplaySettings(root)
        self.display.configure_window()
        px = self.display.pixels
        self.style = apply_dark_theme(root, scale=self.display.scale)
        self.store = ProgressStore(
            DATA_FILE, (exercise["id"] for exercise in EXERCISES)
        )
        self.data = self.load()
        self.current = None
        self.mock = None
        self.deadline = None
        self.result_queue = queue.Queue()
        self.running = False
        self.last_results = {}
        self.reset_versions = {}
        self._closing = False
        self._tick_after = self._poll_after = None

        header = ttk.Frame(root, padding=px(10))
        header.pack(fill="x")
        ttk.Label(header, text="PYTHON PRACTICE", font=("Segoe UI", 18, "bold")).pack(
            side="left"
        )
        self.status = ttk.Label(header, text="", style="Muted.TLabel")
        self.status.pack(side="right")
        controls = ttk.Frame(root, padding=(px(10), 0, px(10), px(8)))
        controls.pack(fill="x")
        self.mock_choice = ttk.Combobox(
            controls, values=list(MOCKS), state="readonly", width=49
        )
        self.mock_choice.current(0)
        self.mock_choice.pack(side="left")
        ttk.Button(controls, text="Start 70-minute mock", command=self.start_mock).pack(
            side="left", padx=px(6)
        )
        ttk.Button(controls, text="Exit mock", command=self.end_mock).pack(side="left")
        self.timer_label = ttk.Label(
            controls, text="Practice mode", style="Muted.TLabel"
        )
        self.timer_label.pack(side="right")

        body = ttk.Panedwindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=px(10), pady=(0, px(10)))
        sidebar = ttk.Frame(body, padding=px(5))
        body.add(sidebar, weight=1)
        ttk.Label(sidebar, text="EXERCISES", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        self.listbox = tk.Listbox(
            sidebar, width=33, exportselection=False, font=("Segoe UI", 10)
        )
        self.listbox.pack(fill="both", expand=True, pady=px(5))
        self.listbox.bind("<<ListboxSelect>>", self.select)
        main = ttk.Frame(body, padding=px(5))
        body.add(main, weight=4)
        self.title = ttk.Label(
            main, font=("Segoe UI", 16, "bold"), wraplength=px(800)
        )
        self.title.pack(anchor="w")
        self.meta = ttk.Label(main, style="Muted.TLabel")
        self.meta.pack(anchor="w", pady=(px(2), px(8)))
        self.description = ttk.Label(main, wraplength=px(800), justify="left")
        self.description.pack(anchor="w", fill="x", pady=(0, px(8)))
        main.bind("<Configure>", self.resize_description)
        self.workspace = ttk.Panedwindow(main, orient="vertical")
        self.workspace.pack(fill="both", expand=True)
        editor_pane = ttk.Frame(self.workspace)
        results_pane = ttk.Frame(self.workspace)
        self.workspace.add(editor_pane, weight=3)
        self.workspace.add(results_pane, weight=1)
        ttk.Label(editor_pane, text="YOUR PYTHON CODE").pack(anchor="w")
        buttons = ttk.Frame(editor_pane)
        buttons.pack(side="bottom", fill="x", pady=(px(4), 0))
        self.editor = self.create_text_pane(
            editor_pane, height=14, font=("Consolas", 11), undo=True, wrap="none",
            text_class=CodeEditor, scale=self.display.scale,
        )
        self.run_button = ttk.Button(
            buttons, text="Run tests", command=self.run_tests, style="Primary.TButton"
        )
        self.run_button.pack(side="left")
        ttk.Button(buttons, text="Save draft", command=self.save_current).pack(
            side="left", padx=px(6)
        )
        ttk.Button(buttons, text="Reset to starter", command=self.reset).pack(
            side="left"
        )
        results_header = ttk.Frame(results_pane, padding=(0, px(4), 0, 0))
        results_header.pack(fill="x")
        ttk.Label(results_header, text="TEST RESULTS").pack(side="left")
        ttk.Label(
            results_header, text="Drag divider to resize", style="Muted.TLabel"
        ).pack(side="right")
        self.results = self.create_text_pane(
            results_pane, height=5, font=("Consolas", 10), state="disabled"
        )
        self.refresh_list()
        self.listbox.selection_set(0)
        self.show_exercise(0)
        self.tick()
        self._poll_after = self.root.after(100, self.poll_results)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def create_text_pane(
        self, parent, text_class=scrolledtext.ScrolledText, **options
    ):
        text = text_class(parent, **options)
        text.frame.configure(background=self.style.lookup("TFrame", "background"))
        # Preserve editor bindings while replacing Windows' light native scrollbar.
        text.vbar.destroy()
        text.vbar = ttk.Scrollbar(
            text.frame, orient="vertical", command=text.yview, takefocus=False
        )
        text.vbar.pack(side="right", fill="y")
        text.configure(yscrollcommand=text.vbar.set)
        text.pack(fill="both", expand=True, pady=self.display.pixels(5))
        return text

    def load(self):
        data = self.store.load()
        if self.store.warning:
            messagebox.showwarning(
                "Could not load progress", self.store.warning, parent=self.root
            )
        return data

    def persist(self):
        try:
            self.store.save(self.data)
            return True
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Could not save progress", str(error), parent=self.root
            )
            return False

    def save_current(self):
        if self.current is not None:
            self.data["drafts"][EXERCISES[self.current]["id"]] = self.editor.get(
                "1.0", "end-1c"
            )
            return self.persist()
        return True

    def resize_description(self, event):
        px = self.display.pixels
        width = max(px(150), event.width - px(12))
        self.title.config(wraplength=width)
        self.description.config(wraplength=width)

    def refresh_list(self):
        indices = self.mock if self.mock is not None else list(range(len(EXERCISES)))
        self.indices = indices
        self.listbox.delete(0, "end")
        for index in indices:
            exercise = EXERCISES[index]
            mark = "✓" if exercise["id"] in self.data["solved"] else "○"
            self.listbox.insert("end", f"{mark}  {index + 1}. {exercise['title']}")
        self.status.config(
            text=f"{len(self.data['solved'])} / {len(EXERCISES)} completed"
        )
        if self.current in indices:
            self.listbox.selection_set(indices.index(self.current))

    def select(self, event=None):
        selection = self.listbox.curselection()
        if selection:
            self.show_exercise(self.indices[selection[0]])

    def show_exercise(self, index, *, save=True):
        if self.current == index:
            return True
        if save and not self.save_current():
            self.refresh_list()
            return False
        self.current = index
        ex = EXERCISES[index]
        self.title.config(text=f"{index + 1}. {ex['title']}")
        self.meta.config(
            text=f"{ex['difficulty'].title()}  •  {ex['skill']}  •  {len(ex['cases'])} test cases"
        )
        self.description.config(text=ex["description"])
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.data["drafts"].get(ex["id"], ex["starter"]))
        self.editor.edit_reset()
        self.set_results(
            self.last_results.get(index, "Write your solution, then select Run tests.")
        )
        return True

    def set_results(self, text):
        self.results.config(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", text)
        self.results.config(state="disabled")

    def reset(self):
        if self.current is None:
            return
        if messagebox.askyesno(
            "Reset draft", "Replace this draft with the starter code?"
        ):
            self.reset_versions[self.current] = (
                self.reset_versions.get(self.current, 0) + 1
            )
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", EXERCISES[self.current]["starter"])
            self.editor.edit_reset()
            self.last_results.pop(self.current, None)
            self.set_results("Draft reset. Write your solution, then select Run tests.")
            self.save_current()

    def run_tests(self):
        if self.running or self.current is None:
            return
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.expire_mock()
            return
        self.save_current()
        index = self.current
        version = self.reset_versions.get(index, 0)
        code = self.editor.get("1.0", "end-1c")
        self.running = True
        self.run_button.config(state="disabled", text="Running…")
        self.set_results("Running tests…")

        def work():
            try:
                result = check(code, EXERCISES[index])
            except Exception as error:
                result = {"error": f"Could not start checker: {error}"}
            self.result_queue.put((index, version, result))

        threading.Thread(target=work, daemon=True).start()

    def poll_results(self):
        if self._closing:
            return
        try:
            index, version, result = self.result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.running = False
            self.run_button.config(state="normal", text="Run tests")
            if "error" in result:
                text = result["error"]
            else:
                cases = result["results"]
                passed = sum(case["passed"] for case in cases)
                text = f"{passed} / {len(cases)} tests passed.\n"
                for number, case in enumerate(cases, 1):
                    text += f"\n{'PASS' if case['passed'] else 'FAIL'} {number}: input {case['input']}\n"
                    if not case["passed"]:
                        text += f"  Expected: {case['expected']}\n  Received: {case['actual']}\n"
                if (
                    passed == len(cases)
                    and EXERCISES[index]["id"] not in self.data["solved"]
                ):
                    self.data["solved"].append(EXERCISES[index]["id"])
                    self.persist()
                    self.refresh_list()
            if result.get("stdout"):
                text += "\n\nPRINT OUTPUT (stdout / stderr)\n" + result["stdout"]
            text = (
                "Results for the last submitted draft; re-run after editing.\n\n" + text
            )
            # A reset invalidates pending display results, not historical completion.
            if version == self.reset_versions.get(index, 0):
                self.last_results[index] = text
                if self.current == index:
                    self.set_results(text)
        self._poll_after = self.root.after(100, self.poll_results)

    def start_mock(self):
        if not messagebox.askyesno(
            "Start mock",
            "Start a 70-minute practice session? Your existing drafts will be available. The timer runs only while the app is open.",
        ):
            return
        if not self.save_current():
            return
        pair = list(MOCKS[self.mock_choice.get()])
        self.show_exercise(pair[0], save=False)
        self.mock = pair
        self.deadline = time.monotonic() + 70 * 60
        self.refresh_list()

    def end_mock(self):
        if self.mock is None:
            return
        self.mock = None
        self.deadline = None
        self.timer_label.config(text="Practice mode")
        self.refresh_list()

    def expire_mock(self):
        self.save_current()
        self.end_mock()
        messagebox.showinfo(
            "Time is up",
            "Your mock has ended. Your drafts and results are still available in practice mode.",
        )

    def tick(self):
        if self._closing:
            return
        if self.deadline is not None:
            remaining = max(0, int(self.deadline - time.monotonic() + 0.999))
            self.timer_label.config(
                text=f"Mock time remaining: {remaining // 60:02d}:{remaining % 60:02d}"
            )
            if remaining == 0:
                self.expire_mock()
        self._tick_after = self.root.after(250, self.tick)

    def close(self):
        if not self.save_current() and not messagebox.askyesno(
            "Unsaved draft",
            "Saving failed. Close anyway and lose unsaved changes?",
            parent=self.root,
        ):
            return
        self._closing = True
        for callback in (self._tick_after, self._poll_after):
            if callback is not None:
                self.root.after_cancel(callback)
        self.root.destroy()


def main():
    enable_windows_dpi_awareness()
    root = tk.Tk()
    PracticeApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
