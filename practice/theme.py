"""Shared dark styling for the desktop interface and its Tk text widgets."""

import ctypes
import sys
from ctypes import wintypes
from tkinter import TclError, ttk


DARK_COLORS = {
    "background": "#171b24",
    "surface": "#202733",
    "foreground": "#e6edf3",
    "muted": "#a4b1c2",
    "disabled": "#8994a5",
    "border": "#3c4759",
    "hover": "#2e394c",
    "pressed": "#374761",
    "accent": "#8ab4f8",
    "accent_hover": "#a5c7ff",
    "accent_pressed": "#6b9ee8",
    "selection": "#365880",
    "syntax_keyword": "#c6a0f6",
    "syntax_string": "#a6d189",
    "syntax_number": "#efb080",
    "syntax_comment": "#8b9bb0",
    "syntax_builtin": "#8ab4f8",
    "syntax_definition": "#7dcfff",
}


def _apply_windows_dark_title_bar(root):
    """Style Tk's native outer window, not its child/client-area HWND."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
        get_ancestor.restype = wintypes.HWND
        hwnd = get_ancestor(root.winfo_id(), 2)  # GA_ROOT
        if not hwnd:
            return False
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        set_attribute = dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
        ]
        set_attribute.restype = ctypes.c_long  # HRESULT
        enabled = wintypes.BOOL(True)
        # Windows 10 releases before 20H1 used attribute 19 instead of 20.
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
            if set_attribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            ) == 0:
                return True
    except (AttributeError, OSError, TclError):
        pass
    return False


def apply_dark_theme(root, scale=1.0):
    colors = DARK_COLORS
    style = ttk.Style(root)
    # Native Windows themes ignore several color settings, so use a portable theme.
    style.theme_use("clam")
    root.configure(background=colors["background"])
    style.configure(
        ".",
        background=colors["background"],
        foreground=colors["foreground"],
        fieldbackground=colors["surface"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        troughcolor=colors["background"],
        selectbackground=colors["selection"],
        selectforeground=colors["foreground"],
        focuscolor=colors["accent"],
    )
    style.map(
        ".",
        background=[
            ("disabled", colors["background"]),
            ("active", colors["hover"]),
        ],
        foreground=[("disabled", colors["disabled"])],
        selectbackground=[("!focus", colors["selection"])],
        selectforeground=[("!focus", colors["foreground"])],
    )
    style.configure("Muted.TLabel", foreground=colors["muted"])
    style.configure(
        "TButton", background=colors["surface"], padding=round(5 * scale)
    )
    style.map(
        "TButton",
        background=[
            ("disabled", colors["surface"]),
            ("pressed", colors["pressed"]),
            ("active", colors["hover"]),
        ],
        bordercolor=[("focus", colors["accent"])],
        lightcolor=[("pressed", colors["border"])],
        darkcolor=[("pressed", colors["border"])],
    )
    style.configure(
        "Primary.TButton", background=colors["accent"],
        foreground=colors["background"], focuscolor=colors["background"],
        bordercolor=colors["accent"],
        lightcolor=colors["accent"], darkcolor=colors["accent"],
    )
    primary_states = [
        ("disabled", colors["surface"]),
        ("pressed", colors["accent_pressed"]),
        ("active", colors["accent_hover"]),
    ]
    style.map(
        "Primary.TButton",
        background=primary_states,
        foreground=[("disabled", colors["disabled"])],
        bordercolor=primary_states,
        lightcolor=primary_states,
        darkcolor=primary_states,
    )
    style.configure(
        "TCombobox", background=colors["surface"], arrowcolor=colors["foreground"],
        padding=max(1, round(scale)),
    )
    style.map(
        "TCombobox",
        background=[("active", colors["hover"])],
        fieldbackground=[
            ("disabled", colors["background"]),
            ("readonly", colors["surface"]),
        ],
        foreground=[
            ("disabled", colors["disabled"]),
            ("readonly", colors["foreground"]),
        ],
        selectbackground=[("readonly", colors["selection"])],
        selectforeground=[("readonly", colors["foreground"])],
        bordercolor=[("focus", colors["accent"])],
        arrowcolor=[("disabled", colors["disabled"])],
    )
    style.configure(
        "TScrollbar", background=colors["border"], arrowcolor=colors["foreground"],
        arrowsize=round(14 * scale),
    )
    style.map(
        "TScrollbar",
        background=[
            ("pressed", colors["pressed"]),
            ("active", colors["hover"]),
        ],
    )

    style.configure("Sash", sashthickness=round(6 * scale))

    # The option database also reaches the combobox's lazily created popup list.
    for widget_class in ("Text", "Listbox"):
        for option, value in {
            "background": colors["surface"],
            "foreground": colors["foreground"],
            "selectBackground": colors["selection"],
            "selectForeground": colors["foreground"],
            "highlightBackground": colors["border"],
            "highlightColor": colors["accent"],
            "highlightThickness": max(1, round(scale)),
            "borderWidth": 0,
            "relief": "flat",
        }.items():
            root.option_add(f"*{widget_class}.{option}", value)
    root.option_add("*Text.insertBackground", colors["foreground"])
    root.option_add("*Text.inactiveSelectBackground", colors["selection"])
    root.option_add("*Listbox.disabledForeground", colors["disabled"])
    root.option_add("*Listbox.selectBorderWidth", 0)
    root.option_add("*Listbox.activeStyle", "none")
    if sys.platform == "win32":
        # Tk creates/recreates its native frame when mapping the toplevel.
        def darken_title_bar(event):
            if event.widget is root:
                _apply_windows_dark_title_bar(root)

        root.bind("<Map>", darken_title_bar, add="+")
    return style
