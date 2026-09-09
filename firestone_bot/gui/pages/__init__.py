"""Page builders: each module exposes `build(parent, ctx) -> frame`."""

from __future__ import annotations

from firestone_bot.gui.context import PageContext

PAGE_ORDER = ["camp", "automations", "journal", "workshop"]
PAGE_TITLES = {
    "camp": "Camp",
    "automations": "Automations",
    "journal": "Journal",
    "workshop": "Workshop",
}


def build(name: str, parent, ctx: PageContext):
    import importlib

    module = {
        "camp": "dashboard",
        "automations": "automations",
        "journal": "journal",
        "workshop": "workshop",
    }[name]
    return importlib.import_module(f"firestone_bot.gui.pages.{module}").build(parent, ctx)


__all__ = ["PAGE_ORDER", "PAGE_TITLES", "PageContext", "build"]
