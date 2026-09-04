"""Page builders: each module exposes `build(parent, ctx) -> frame`."""

from __future__ import annotations

from firestone_bot.gui.context import PageContext

PAGE_ORDER = ["dashboard", "main", "town", "guild", "missions", "advanced", "help"]
PAGE_TITLES = {
    "dashboard": "Dashboard",
    "main": "Main screen",
    "town": "Town",
    "guild": "Guild & Tree",
    "missions": "Missions & WM",
    "advanced": "Advanced",
    "help": "Help",
}


def build(name: str, parent, ctx: PageContext):
    import importlib

    module = {
        "dashboard": "dashboard",
        "main": "main_screen",
        "town": "town",
        "guild": "guild_tree",
        "missions": "missions_wm",
        "advanced": "advanced",
        "help": "help",
    }[name]
    return importlib.import_module(f"firestone_bot.gui.pages.{module}").build(parent, ctx)


__all__ = ["PAGE_ORDER", "PAGE_TITLES", "PageContext", "build"]
