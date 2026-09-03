"""Port of Functions/ClaimEngineer.ahk: war machine upgrades (optional) and claim tools."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_engineer(g: Game) -> None:
    g.focus()
    # open engineer
    g.move_to(atlas.TOWN_ENGINEER)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # check if option to level WM's is chosen
    if g.settings.UpgradeWM != "Don't Upgrade WM's":
        from firestone_bot.features.wm_upgrade import wm_upgrade

        g.move_to(atlas.ENGINEER_WM_TAB)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        wm_upgrade(g)
        # open engineer
        g.move_to(atlas.ENGINEER_TAB)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
    else:
        # select engineer
        g.move_to(atlas.ENGINEER_SELECT)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
    # ClaimTools:
    if g.found(atlas.ENGINEER_TOOLS_READY):
        g.move_to(atlas.ENGINEER_TOOLS_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    big_close(g)
