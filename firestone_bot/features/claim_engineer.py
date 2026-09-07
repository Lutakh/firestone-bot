"""Port of Functions/ClaimEngineer.ahk: war machine upgrades (optional) and claim tools."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_engineer(g: Game) -> None:
    g.focus()
    g.status("Engineer: opening the garage")
    # The garage is a full-screen dialog with the standard X; a newly unlocked war machine
    # plays an intro animation in it (2026-09-08), so the entry is verified and the screen
    # left to settle before the tabs are clicked.
    g.require_screen(atlas.TOWN_ENGINEER, atlas.DIALOG_CLOSE_X, via_town=True)
    g.wait_still()
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
        g.status("Engineer: claiming the tools")
        g.tap(atlas.ENGINEER_TOOLS_CLAIM, 1000)
    big_close(g)
