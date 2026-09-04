"""Town page: guardian, tavern, oracle, engineer, exotic merchant, arena, alchemist, research."""

from __future__ import annotations

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui import theme
from firestone_bot.gui.catalog import (
    CHAOS_GUARDIAN_CHOICES,
    OPTIONS,
    SELL_KEYS,
    SELL_LABELS,
)
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import (
    Card,
    LinkButton,
    OrderedList,
    RadioGroup,
    page_frame,
    page_title,
    place_card,
)


def build(parent, ctx: PageContext):
    page, content = page_frame(parent)
    page_title(
        content,
        "Town",
        "Town buildings, visited in this order every cycle: Guardian, Tavern, Oracle, Engineer, "
        "Exotic merchant, Arena, Alchemist, Research.",
    )
    s = ctx.settings

    guardian = place_card(Card(content, ctx, "Guardian"))
    guardian.option("GuardianTrain")
    opt = OPTIONS["ChaosGuardianOrder"]
    guardian.row(
        opt.label,
        opt.help,
        lambda p: OrderedList(
            p, ctx, CHAOS_GUARDIAN_CHOICES, key="ChaosGuardianOrder", display=opt.display
        ),
    )

    tavern = place_card(Card(content, ctx, "Tavern"))
    tavern.option("Token")
    tokens = tavern.option("MaxTokens")
    tavern.option("Beer")
    tavern.option("Scarab")
    scarab = tavern.option("MaxScarab")

    def tick_tavern():
        tokens.control.set_live(f"used today: {daily._int(s, 'TokenCountDaily')}")
        scarab.control.set_live(f"played today: {daily._int(s, 'ScarabCountDaily')}")

    tick_tavern()
    ctx.register_tick(tick_tavern)

    oracle = place_card(Card(content, ctx, "Oracle", master="SkipOracle"))
    oracle.option("Bless")
    oracle.option("DailyOracle")

    engineer = place_card(Card(content, ctx, "Engineer"))
    engineer.option("NoEng")
    link = LinkButton(engineer.body, "War machine upgrades…", lambda: ctx.show_page("missions"))
    engineer.add(link, always_enabled=True, pady=(0, 2))

    merchant = place_card(Card(content, ctx, "Exotic merchant", master="SellEx"))
    merchant.row(
        "Selling strategy",
        "Exactly one is active; the four keys are written as 1/0.",
        lambda p: RadioGroup(p, ctx, SELL_KEYS, SELL_LABELS),
    )
    merchant.option("ExoticUpgrades")
    merchant.option("BuyEx")

    arena = place_card(Card(content, ctx, "Arena"))
    pvp = arena.option("PVP")
    badge = ctk.CTkLabel(
        pvp.holder, text="", font=theme.font(12, "bold"), text_color=theme.MUTED, anchor="e"
    )
    badge.pack(side="left", padx=(0, 12), before=pvp.control_widget)

    def tick_arena():
        done = daily.arena_done(s)
        text, colour = ("done today", theme.OK) if done else ("pending", theme.MUTED)
        if badge.cget("text") != text:
            badge.configure(text=text, text_color=colour)

    tick_arena()
    ctx.register_tick(tick_arena)

    alch = place_card(Card(content, ctx, "Alchemist", master="Alch"))
    alch.option("DragonBlood")
    alch.option("Dust")
    alch.option("Coin")

    research = place_card(Card(content, ctx, "Research"))
    research.option("Research")
    return page
