"""Semantic colours and fonts of the customtkinter GUI.

Colours are ``(light, dark)`` tuples so every widget follows the appearance mode.
"""

from __future__ import annotations

OK = ("#1f9d55", "#3ddc84")
WARN = ("#c77700", "#ffb454")
ERR = ("#c0392b", "#ff6b6b")
INFO = ("#2b6cb0", "#63b3ed")
MUTED = ("gray40", "gray60")
NEUTRAL = ("gray55", "gray50")

# Subtle strip backgrounds for banners (light, dark).
BANNER_BG = {
    "ok": ("#e3f6ea", "#173d2a"),
    "warn": ("#fff1dc", "#3d2f14"),
    "err": ("#fde3e1", "#3f1f1f"),
    "info": ("#e1ecfa", "#1b2c42"),
}

KIND_COLOUR = {"ok": OK, "warn": WARN, "err": ERR, "info": INFO, "muted": MUTED, "grey": NEUTRAL}

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

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
