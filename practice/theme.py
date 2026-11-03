"""Shared dark styling for the desktop interface and its Tk text widgets."""

from tkinter import ttk


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
    "selection": "#365880",
}


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
    return style
