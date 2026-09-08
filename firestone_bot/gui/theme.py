"""Retro console design tokens and native customtkinter theme.

Colours are ``(light, dark)`` tuples so every widget follows the appearance mode.
"""

from __future__ import annotations

import sys

# Warm enamel, graphite instrument panels and brass highlights.
PAPER = ("#ded2b8", "#242520")
SURFACE = ("#eee4cf", "#32332c")
INK = ("#302e27", "#eee4cf")
BORDER = ("#a99b7e", "#77725e")
GRAPHITE = "#2d2e28"
GRAPHITE_HOVER = "#44453a"
CREAM = "#f0e5cb"
BRASS = "#e5b52c"
BRASS_HOVER = "#f2cc58"
OK = ("#426c2c", "#aac57e")
WARN = ("#875914", "#efc564")
ERR = ("#a63e25", "#ee957d")
INFO = ("#756017", "#e5c36d")
MUTED = ("#6c6250", "#c0b69f")
NEUTRAL = ("#746d5b", "#b7ad94")
STOP = "#a43d25"
STOP_HOVER = "#bf4b2e"

BANNER_BG = {
    "ok": ("#e1e7c9", "#2e3b27"),
    "warn": ("#f1dfb1", "#473a20"),
    "err": ("#f3d9ca", "#492f28"),
    "info": ("#e8ddb9", "#3e3927"),
}
KIND_COLOUR = {"ok": OK, "warn": WARN, "err": ERR, "info": INFO, "muted": MUTED, "grey": NEUTRAL}

FONT_FAMILY = "Helvetica" if sys.platform == "darwin" else "Segoe UI"
MONO_FAMILY = "Menlo" if sys.platform == "darwin" else "Consolas"
DISPLAY_FAMILY = "Courier New"


def install() -> None:
    """Install the complete native-widget palette before creating any windows.

    Start from CTk's supported built-in theme so all required widget keys remain
    present. Every control, including lazily built pages and dialogs, inherits it.
    """
    import customtkinter as ctk

    ctk.set_default_color_theme("dark-blue")
    palette = ctk.ThemeManager.theme
    replacements = {
        "CTk": {"fg_color": PAPER},
        "CTkToplevel": {"fg_color": PAPER},
        "CTkFrame": {
            "fg_color": SURFACE,
            "top_fg_color": SURFACE,
            "border_color": BORDER,
            "corner_radius": 5,
        },
        "CTkLabel": {"text_color": INK},
        "CTkButton": {
            "fg_color": GRAPHITE,
            "hover_color": GRAPHITE_HOVER,
            "text_color": CREAM,
            "text_color_disabled": "#9b9788",
            "border_color": BORDER,
            "border_width": 2,
            "corner_radius": 4,
        },
        "CTkEntry": {
            "fg_color": SURFACE,
            "text_color": INK,
            "border_color": BORDER,
            "placeholder_text_color": MUTED,
            "corner_radius": 3,
        },
        "CTkCheckBox": {
            "fg_color": GRAPHITE,
            "hover_color": GRAPHITE_HOVER,
            "border_color": BORDER,
            "checkmark_color": BRASS,
            "text_color": INK,
            "text_color_disabled": MUTED,
            "corner_radius": 3,
        },
        "CTkSwitch": {
            "fg_color": BORDER,
            "progress_color": BRASS,
            "button_color": GRAPHITE,
            "button_hover_color": GRAPHITE_HOVER,
            "text_color": INK,
            "text_color_disabled": MUTED,
            "corner_radius": 4,
        },
        "CTkRadioButton": {
            "fg_color": INFO,
            "hover_color": BRASS,
            "border_color": BORDER,
            "text_color": INK,
            "text_color_disabled": MUTED,
        },
        "CTkProgressBar": {"fg_color": BORDER, "progress_color": INFO, "corner_radius": 2},
        "CTkSlider": {
            "fg_color": BORDER,
            "progress_color": INFO,
            "button_color": GRAPHITE,
            "button_hover_color": GRAPHITE_HOVER,
        },
        "CTkOptionMenu": {
            "fg_color": GRAPHITE,
            "button_color": GRAPHITE_HOVER,
            "button_hover_color": "#595a4b",
            "text_color": CREAM,
            "text_color_disabled": "#aba591",
            "corner_radius": 3,
        },
        "CTkComboBox": {
            "fg_color": SURFACE,
            "border_color": BORDER,
            "button_color": BORDER,
            "button_hover_color": BRASS,
            "text_color": INK,
            "text_color_disabled": MUTED,
        },
        "CTkScrollbar": {"button_color": BORDER, "button_hover_color": INFO},
        "CTkSegmentedButton": {
            "fg_color": BORDER,
            "selected_color": GRAPHITE,
            "selected_hover_color": GRAPHITE_HOVER,
            "unselected_color": "#66624f",
            "unselected_hover_color": "#79745e",
            "text_color": CREAM,
            "text_color_disabled": "#c0b69f",
            "corner_radius": 3,
        },
        "CTkTextbox": {
            "fg_color": GRAPHITE,
            "text_color": CREAM,
            "border_color": BORDER,
            "border_width": 1,
            "corner_radius": 4,
            "scrollbar_button_color": "#79745e",
            "scrollbar_button_hover_color": BRASS,
        },
        "CTkScrollableFrame": {"label_fg_color": SURFACE},
        "DropdownMenu": {"fg_color": SURFACE, "hover_color": BORDER, "text_color": INK},
    }
    for widget, values in replacements.items():
        palette[widget].update(values)
    palette["CTkFont"].update(family=FONT_FAMILY, size=13)


_fonts: dict[tuple[str, int, str], object] = {}


def font(size: int = 13, weight: str = "normal", family: str = FONT_FAMILY):
    """Cached ``CTkFont`` (must be called after the root window exists)."""
    import customtkinter as ctk

    key = (family, size, weight)
    if key not in _fonts:
        _fonts[key] = ctk.CTkFont(family=family, size=size, weight=weight)
    return _fonts[key]


def colour(kind: str):
    return KIND_COLOUR.get(kind, MUTED)
