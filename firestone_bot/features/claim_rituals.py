"""Port of Functions/ClaimRituals.ahk: Oracle rituals, then blessings and the daily gift."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.oracle_daily import oracle_daily
from firestone_bot.features.upgrade_blessings import upgrade_blessings
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_rituals(g: Game) -> None:
    g.focus()
    # open Oracle in town
    g.tap(atlas.TOWN_ORACLE)
    # open Rituals tab in Oracle if ready
    if g.settings.flag("Rituals") and g.found(atlas.RITUALS_DOT):
        g.tap(atlas.RITUALS_TAB)
        # cycle through rituals
        for probe, button in atlas.RITUAL_CLAIMS:
            if g.found(probe):
                g.tap(button, 1000)
    # check if upgradeBlessings box was checked
    if g.settings.flag("Bless"):
        upgrade_blessings(g)
    # check if Claim Daily Oracle was checked on startup
    if g.settings.flag("DailyOracle"):
        oracle_daily(g)
    big_close(g)
