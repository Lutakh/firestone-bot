"""Three native skins sharing the same semantic palette and interface layout.

Colours are (light, dark) tuples. Changing a skin affects newly built widgets;
MainWindow rebuilds its views while retaining settings and runtime state.
"""

from __future__ import annotations

import sys
import tkinter as tk

SKIN_NAMES = ("Fieldbook", "Retro", "Futuristic")
FONT_FAMILY = "Helvetica" if sys.platform == "darwin" else "Segoe UI"
MONO_FAMILY = "Menlo" if sys.platform == "darwin" else "Consolas"

_PALETTES = {
    "Fieldbook": {
        "PAPER": ("#f4f0e6", "#17251f"),
        "SURFACE": ("#fffaf0", "#22352c"),
        "SURFACE_ALT": ("#ece5d6", "#2c4135"),
        "BORDER": ("#cec3ae", "#4a6051"),
        "TEXT": ("#203c2e", "#f1eadb"),
        "MUTED": ("#6c7063", "#b4bdae"),
        "ACCENT": ("#ad4e35", "#d88263"),
        "ACCENT_HOVER": ("#913d29", "#e29b80"),
        "ON_ACCENT": ("#fffaf0", "#18251f"),
        "HEADER": ("#203c2e", "#102017"),
        "ON_HEADER": ("#fff6e1", "#fff6e1"),
        "HEADER_MUTED": ("#bdc8b9", "#bdc8b9"),
        "INPUT_BG": ("#fffcf5", "#192a22"),
        "OK": ("#427244", "#9ac49b"),
        "WARN": ("#91631b", "#dfbc77"),
        "ERR": ("#a53b2d", "#f09c8f"),
        "INFO": ("#3d7067", "#94c6b8"),
        "NEUTRAL": ("#777a69", "#a5ae9d"),
        "DISPLAY_FAMILY": "Georgia",
        "RADIUS": 12,
    },
    "Retro": {
        "PAPER": ("#ded2b8", "#252620"),
        "SURFACE": ("#eee4cf", "#34352d"),
        "SURFACE_ALT": ("#e0d3b7", "#404137"),
        "BORDER": ("#a99b7e", "#74725e"),
        "TEXT": ("#302e27", "#eee4cf"),
        "MUTED": ("#6c6250", "#c0b69f"),
        "ACCENT": ("#755617", "#e5b52c"),
        "ACCENT_HOVER": ("#5e4310", "#f2cc58"),
        "ON_ACCENT": ("#fff3d1", "#272820"),
        "HEADER": ("#2d2e28", "#1c1e19"),
        "ON_HEADER": ("#edbd35", "#edbd35"),
        "HEADER_MUTED": ("#c1bba5", "#c1bba5"),
        "INPUT_BG": ("#f7ecd5", "#252720"),
        "OK": ("#496c2c", "#aac57e"),
        "WARN": ("#875914", "#efc564"),
        "ERR": ("#a63e25", "#ee957d"),
        "INFO": ("#756017", "#e5c36d"),
        "NEUTRAL": ("#746d5b", "#b7ad94"),
        "DISPLAY_FAMILY": "Courier New",
        "RADIUS": 4,
    },
    "Futuristic": {
        "PAPER": ("#e9f1f6", "#101b2b"),
        "SURFACE": ("#f6fbff", "#18283b"),
        "SURFACE_ALT": ("#dce9f1", "#21364b"),
        "BORDER": ("#aac2d0", "#36546c"),
        "TEXT": ("#153a4f", "#dff3ff"),
        "MUTED": ("#536f80", "#9bb9cf"),
        "ACCENT": ("#006d85", "#56d6ef"),
        "ACCENT_HOVER": ("#00576c", "#83e5f6"),
        "ON_ACCENT": ("#f4fdff", "#102332"),
        "HEADER": ("#10273b", "#0a1421"),
        "ON_HEADER": ("#6cddf4", "#6cddf4"),
        "HEADER_MUTED": ("#a6bfce", "#a6bfce"),
        "INPUT_BG": ("#ffffff", "#101f30"),
        "OK": ("#237958", "#78dfb0"),
        "WARN": ("#916019", "#f5c56f"),
        "ERR": ("#af3852", "#ff9eb5"),
        "INFO": ("#006d85", "#56d6ef"),
        "NEUTRAL": ("#617886", "#a0b6c6"),
        "DISPLAY_FAMILY": FONT_FAMILY,
        "RADIUS": 7,
    },
}

# Public semantic tokens are populated together by _apply_tokens.
PAPER: tuple[str, str] = _PALETTES["Fieldbook"]["PAPER"]
SURFACE: tuple[str, str] = _PALETTES["Fieldbook"]["SURFACE"]
SURFACE_ALT: tuple[str, str] = _PALETTES["Fieldbook"]["SURFACE_ALT"]
BORDER: tuple[str, str] = _PALETTES["Fieldbook"]["BORDER"]
TEXT: tuple[str, str] = _PALETTES["Fieldbook"]["TEXT"]
MUTED: tuple[str, str] = _PALETTES["Fieldbook"]["MUTED"]
ACCENT: tuple[str, str] = _PALETTES["Fieldbook"]["ACCENT"]
ACCENT_HOVER: tuple[str, str] = _PALETTES["Fieldbook"]["ACCENT_HOVER"]
ON_ACCENT: tuple[str, str] = _PALETTES["Fieldbook"]["ACCENT"]
HEADER: tuple[str, str] = _PALETTES["Fieldbook"]["HEADER"]
ON_HEADER: tuple[str, str] = _PALETTES["Fieldbook"]["HEADER"]
HEADER_MUTED: tuple[str, str] = _PALETTES["Fieldbook"]["MUTED"]
INPUT_BG: tuple[str, str] = _PALETTES["Fieldbook"]["INPUT_BG"]
OK: tuple[str, str] = _PALETTES["Fieldbook"]["OK"]
WARN: tuple[str, str] = _PALETTES["Fieldbook"]["WARN"]
ERR: tuple[str, str] = _PALETTES["Fieldbook"]["ERR"]
INFO: tuple[str, str] = _PALETTES["Fieldbook"]["INFO"]
NEUTRAL: tuple[str, str] = _PALETTES["Fieldbook"]["NEUTRAL"]
DISPLAY_FAMILY: str = _PALETTES["Fieldbook"]["DISPLAY_FAMILY"]
RADIUS: int = _PALETTES["Fieldbook"]["RADIUS"]

_skin = "Fieldbook"
_fonts: dict[tuple[str, int, str], object] = {}
_font_root = None


def current_skin() -> str:
    return _skin


def _apply_tokens(name: str) -> None:
    global BANNER_BG, KIND_COLOUR
    globals().update(_PALETTES[name])
    # State foregrounds stay readable on the subtle surface in both appearances.
    BANNER_BG = {kind: SURFACE_ALT for kind in ("ok", "warn", "err", "info")}
    KIND_COLOUR = {
        "ok": OK,
        "warn": WARN,
        "err": ERR,
        "info": INFO,
        "muted": MUTED,
        "grey": NEUTRAL,
    }


def set_skin(name: str) -> None:
    """Select a supported skin and install defaults for every CTk widget type.

    This function does not change appearance mode or touch game settings. It is
    safe before creating a Tk root. Unknown names leave the current skin intact.
    """
    global _skin
    if name not in SKIN_NAMES:
        raise ValueError(f"Unknown interface skin: {name!r}")
    import customtkinter as ctk

    _skin = name
    _apply_tokens(name)
    ctk.set_default_color_theme("dark-blue")
    palette = ctk.ThemeManager.theme
    replacements = {
        "CTk": {"fg_color": PAPER},
        "CTkToplevel": {"fg_color": PAPER},
        "CTkFrame": {
            "fg_color": SURFACE,
            "top_fg_color": SURFACE,
            "border_color": BORDER,
            "corner_radius": RADIUS,
        },
        "CTkLabel": {"text_color": TEXT},
        "CTkButton": {
            "fg_color": ACCENT,
            "hover_color": ACCENT_HOVER,
            "text_color": ON_ACCENT,
            "text_color_disabled": MUTED,
            "border_color": BORDER,
            "border_width": 0,
            "corner_radius": RADIUS,
        },
        "CTkEntry": {
            "fg_color": INPUT_BG,
            "text_color": TEXT,
            "border_color": BORDER,
            "placeholder_text_color": MUTED,
            "corner_radius": max(3, RADIUS - 3),
        },
        "CTkCheckBox": {
            "fg_color": ACCENT,
            "hover_color": ACCENT_HOVER,
            "border_color": BORDER,
            "checkmark_color": ON_ACCENT,
            "text_color": TEXT,
            "text_color_disabled": MUTED,
            "corner_radius": 3,
        },
        "CTkSwitch": {
            "fg_color": BORDER,
            "progress_color": ACCENT,
            "button_color": INPUT_BG,
            "button_hover_color": SURFACE_ALT,
            "text_color": TEXT,
            "text_color_disabled": MUTED,
        },
        "CTkRadioButton": {
            "fg_color": ACCENT,
            "hover_color": ACCENT_HOVER,
            "border_color": BORDER,
            "text_color": TEXT,
            "text_color_disabled": MUTED,
        },
        "CTkProgressBar": {"fg_color": BORDER, "progress_color": ACCENT, "corner_radius": 3},
        "CTkSlider": {
            "fg_color": BORDER,
            "progress_color": ACCENT,
            "button_color": ACCENT,
            "button_hover_color": ACCENT_HOVER,
        },
        "CTkOptionMenu": {
            "fg_color": SURFACE_ALT,
            "button_color": BORDER,
            "button_hover_color": SURFACE_ALT,
            "text_color": TEXT,
            "text_color_disabled": MUTED,
            "corner_radius": max(3, RADIUS - 3),
        },
        "CTkComboBox": {
            "fg_color": INPUT_BG,
            "border_color": BORDER,
            "button_color": BORDER,
            "button_hover_color": SURFACE_ALT,
            "text_color": TEXT,
            "text_color_disabled": MUTED,
        },
        "CTkScrollbar": {"button_color": BORDER, "button_hover_color": ACCENT},
        "CTkSegmentedButton": {
            "fg_color": BORDER,
            "selected_color": BORDER,
            "selected_hover_color": SURFACE_ALT,
            "unselected_color": SURFACE_ALT,
            "unselected_hover_color": BORDER,
            "text_color": TEXT,
            "text_color_disabled": MUTED,
            "corner_radius": max(3, RADIUS - 3),
        },
        "CTkTextbox": {
            "fg_color": INPUT_BG,
            "text_color": TEXT,
            "border_color": BORDER,
            "border_width": 1,
            "corner_radius": RADIUS,
            "scrollbar_button_color": BORDER,
            "scrollbar_button_hover_color": ACCENT,
        },
        "CTkScrollableFrame": {"label_fg_color": SURFACE},
        "DropdownMenu": {"fg_color": SURFACE, "hover_color": SURFACE_ALT, "text_color": TEXT},
    }
    for widget, values in replacements.items():
        palette[widget].update(values)
    palette["CTkFont"].update(family=FONT_FAMILY, size=13)


def font(size: int = 13, weight: str = "normal", family: str | None = None):
    """Cache fonts for the current Tcl interpreter, never reuse a destroyed root's fonts."""
    global _font_root
    import customtkinter as ctk

    root = tk._default_root
    if root is None:
        raise RuntimeError("Create a Tk root before requesting interface fonts")
    if _font_root is not root:
        _fonts.clear()
        _font_root = root
    key = (family or FONT_FAMILY, size, weight)
    if key not in _fonts:
        _fonts[key] = ctk.CTkFont(family=key[0], size=size, weight=weight)
    return _fonts[key]


def heading(size: int = 26):
    return font(size, "normal" if _skin == "Fieldbook" else "bold", DISPLAY_FAMILY)


def mono(size: int = 12):
    return font(size, family=MONO_FAMILY)


def colour(kind: str):
    return KIND_COLOUR.get(kind, MUTED)


_apply_tokens(_skin)
