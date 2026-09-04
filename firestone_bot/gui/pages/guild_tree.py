"""Guild & personal tree page."""

from __future__ import annotations

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui.catalog import OPTIONS, TREE_GROUPS, TREE_KEYS
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import Card, CheckGrid, page_frame, page_title, place_card


def build(parent, ctx: PageContext):
    page, content = page_frame(parent)
    page_title(content, "Guild & Tree", "Guild visit and the personal tree upgrades.")
    s = ctx.settings

    guild = place_card(Card(content, ctx, "Guild", master="NoGuild"))
    for key in ("GuildExpedition", "GNotif", "Pickaxes", "Crystal", "Awaken", "Chaos"):
        guild.option(key)
    crystal = guild.option("MaxCrystals")
    chaos = guild.option("MaxChaos")
    guild.option("ChaosBooks")

    def tick_chaos():
        chaos.control.set_live(f"hits today: {daily._int(s, 'ChaosCountDaily')}")
        crystal.control.set_live(f"hits today: {daily._int(s, 'CrystalCountDaily')}")

    tick_chaos()
    ctx.register_tick(tick_chaos)

    tree = place_card(Card(content, ctx, "Personal tree", master="PTree"))
    cols = ctk.CTkFrame(tree.body, fg_color="transparent")
    grids: list[CheckGrid] = []
    for i, (heading, keys) in enumerate(TREE_GROUPS.items()):
        g = CheckGrid(cols, ctx, [(k, OPTIONS[k].label) for k in keys], columns=1, heading=heading)
        g.widget.grid(row=0, column=i, sticky="new", padx=(0, 16))
        cols.grid_columnconfigure(i, weight=1, uniform="tree")
        grids.append(g)

    class _Cols:
        widget = cols

        @staticmethod
        def set_enabled(enabled: bool) -> None:
            for g in grids:
                g.set_enabled(enabled)

    tree.add(_Cols())
    footer = tree.note("")

    def tick_tree():
        n = sum(1 for k in TREE_KEYS if s.flag(k))
        text = f"{n} of {len(TREE_KEYS)} upgrades selected"
        if footer.cget("text") != text:
            footer.configure(text=text)

    tick_tree()
    ctx.register_tick(tick_tree)
    return page
