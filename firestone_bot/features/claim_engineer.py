"""Port of Functions/ClaimEngineer.ahk: war machine upgrades (optional) and claim tools."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_engineer(g: Game) -> None:
    g.focus()
    # open engineer
    g.tap(atlas.TOWN_ENGINEER)
    # check if option to level WM's is chosen
    if g.settings.UpgradeWM != "Don't Upgrade WM's":
        from firestone_bot.features.wm_upgrade import wm_upgrade

        g.tap(atlas.ENGINEER_WM_TAB)
        wm_upgrade(g)
        # open engineer
        g.tap(atlas.ENGINEER_TAB)
    else:
        # select engineer
        g.tap(atlas.ENGINEER_SELECT)
    # ClaimTools:
    if g.settings.flag("EngineerTools") and g.found(atlas.ENGINEER_TOOLS_READY):
        g.tap(atlas.ENGINEER_TOOLS_CLAIM, 1000)
    big_close(g)
