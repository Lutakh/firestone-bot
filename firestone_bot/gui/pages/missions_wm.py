"""Missions & war machines page."""

from __future__ import annotations

from firestone_bot.gui.catalog import WM_NONE
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import Card, page_frame, page_title, place_card


def build(parent, ctx: PageContext):
    page, content = page_frame(parent)
    page_title(content, "Missions & WM", "Map missions, campaign and war machine upgrades.")
    s = ctx.settings

    missions = place_card(
        Card(
            content,
            ctx,
            "Map missions",
            master="MapMissions",
        )
    )
    missions.option("MapOpen")
    missions.option("MapHotkey", width=80)
    missions.option("MapReset")

    campaign = place_card(Card(content, ctx, "Campaign", master="Campaign"))
    campaign.option("Liberation")
    campaign.option("DungeonQuest")

    wm = place_card(Card(content, ctx, "War machines (at the engineer)"))
    banner = wm.banner(
        "warn",
        "Engineer visits are off (Town > Engineer), so war machines will not be upgraded.",
        "Turn on",
        lambda: ctx.binder.set_many({"NoEng": "0"}),
        visible=False,
    )
    wm.note("Upgrades happen during the engineer visit: Town > Engineer must be on.")
    which = wm.option("UpgradeWM")
    mode = wm.option("WMOptions")
    blueprints = wm.option("Blueprints")

    def sync(*_):
        upgrading = s.get("UpgradeWM") != WM_NONE
        mode.set_enabled(upgrading)
        blueprints.set_enabled(upgrading and s.get("WMOptions") != "Level Only")
        banner.set_visible(upgrading and s.flag("NoEng"))

    which.control.var.trace_add("write", sync)
    mode.control.var.trace_add("write", sync)
    ctx.binder.var("NoEng", True).trace_add("write", sync)
    sync()

    talents = place_card(Card(content, ctx, "Talents (legacy)"))
    for key in ("Talents450", "Talents800"):
        row = talents.option(key, width=300)
        row.set_enabled(False)
    return page
