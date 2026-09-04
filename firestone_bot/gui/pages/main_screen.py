"""Main screen page: claims, chests, hero upgrades."""

from __future__ import annotations

from firestone_bot.gui.catalog import HERO_TARGET_KEYS, OPTIONS
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import Card, CheckGrid, page_frame, page_title, place_card


def build(parent, ctx: PageContext):
    page, content = page_frame(parent)
    page_title(
        content,
        "Main screen",
        "What the bot claims and opens on the main screen at the start of every cycle, and the "
        "hero upgrades at the end.",
    )

    card = place_card(Card(content, ctx, "Claims"))
    for key in ("Events", "Quests", "Mail", "Shop"):
        card.option(key)

    chests = place_card(Card(content, ctx, "Chests (bag)", master="Chests"))
    for key in ("GearChestExclude", "JewelChestExclude", "CelestialChestExclude"):
        chests.option(key)
    blessing = chests.option("BlessingChests", always_enabled=True)

    def grey_blessing(*_):
        # Only meaningful when the master is OFF: grey it while Chests is ON.
        blessing.set_enabled(not chests.master_on())

    chests.master_switch.var.trace_add("write", grey_blessing)
    grey_blessing()

    heroes = place_card(Card(content, ctx, "Hero upgrades", master="NoHero"))
    heroes.option("NextMilestone")
    heroes.row(
        "Targets",
        "Which rows of the hero panel receive upgrades.",
        lambda p: _targets(p, ctx),
    )
    return page


def _targets(parent, ctx: PageContext) -> CheckGrid:
    return CheckGrid(parent, ctx, [(k, OPTIONS[k].label) for k in HERO_TARGET_KEYS], columns=3)
