"""Help page: requirements, where things are, shortcuts, about."""

from __future__ import annotations

import platform

import customtkinter as ctk

from firestone_bot import __version__
from firestone_bot.gui import theme
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.help_text import HOME_SECTIONS, SHORTCUTS, WHERE_THINGS_ARE
from firestone_bot.gui.widgets import Card, autowrap, page_frame, page_title, place_card


def build(parent, ctx: PageContext):
    page, content = page_frame(parent)
    page_title(content, f"Firestone Bot {__version__} (Python port)", "Requirements and help.")

    req = place_card(Card(content, ctx, "Requirements"))
    bodies = []
    for title, body in HOME_SECTIONS:
        ctk.CTkLabel(req.body, text=title, anchor="w", font=theme.font(13, "bold")).grid(
            sticky="w", pady=(8, 0)
        )
        lbl = ctk.CTkLabel(
            req.body,
            text=body,
            anchor="w",
            justify="left",
            wraplength=860,
            font=theme.font(13),
        )
        lbl.grid(sticky="w")
        bodies.append(lbl)
    autowrap(req.body, bodies, offset=8)

    where = place_card(Card(content, ctx, "Where things are"))
    where.note(WHERE_THINGS_ARE, kind="grey")

    keys = place_card(Card(content, ctx, "Shortcuts"))
    grid = ctk.CTkFrame(keys.body, fg_color="transparent")
    for i, (combo, what) in enumerate(SHORTCUTS):
        ctk.CTkLabel(grid, text=combo, anchor="w", font=theme.font(13, "bold"), width=150).grid(
            row=i, column=0, sticky="w", pady=2
        )
        ctk.CTkLabel(grid, text=what, anchor="w", font=theme.font(13)).grid(
            row=i, column=1, sticky="w", padx=(12, 0), pady=2
        )
    keys.add(grid, always_enabled=True)

    about = place_card(Card(content, ctx, "About"))
    about.note(
        f"Firestone Bot {__version__} · Python {platform.python_version()} · "
        f"customtkinter {ctk.__version__}",
        kind="grey",
    )
    about.buttons(
        ("Open log file", lambda: ctx.call("open_log")),
        ("Open settings folder", lambda: ctx.call("open_folder")),
    )
    return page
