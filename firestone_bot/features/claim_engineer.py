"""Port of Functions/ClaimEngineer.ahk: war machine upgrades (optional) and claim tools."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_engineer(g: Game) -> None:
    g.focus()
    g.status("Engineer: opening the engineer building")
    # The building opens a chooser (Engineer / Garage / Training base) since level 50; the
    # chosen card opens a full-screen page with the standard X. A newly unlocked war
    # machine plays an intro animation there (2026-09-08), so each entry is verified and
    # the page left to settle before anything is clicked.
    g.require_screen(atlas.TOWN_ENGINEER, atlas.ENGINEER_CLOSE_X, via_town=True)
    # check if option to level WM's is chosen
    if g.settings.UpgradeWM != "Don't Upgrade WM's":
        from firestone_bot.features.wm_upgrade import wm_upgrade

        g.status("Engineer: opening the garage")
        g.tap(atlas.ENGINEER_WM_TAB, expect=atlas.DIALOG_CLOSE_X)
        g.wait_still()
        wm_upgrade(g)
        # open engineer
        g.tap(atlas.ENGINEER_TAB)
    else:
        g.status("Engineer: opening the engineer page")
        g.tap(atlas.ENGINEER_SELECT, expect=atlas.DIALOG_CLOSE_X)
        g.wait_still()
    # ClaimTools:
    if g.settings.flag("EngineerTools") and g.found(atlas.ENGINEER_TOOLS_READY):
        g.status("Engineer: claiming the tools")
        g.tap(atlas.ENGINEER_TOOLS_CLAIM, 1000)
    big_close(g)
