"""Port of Functions/Quests.ahk: claim daily and weekly quest rewards.

NOTE: in the AHK file the function's closing brace comes BEFORE `BigClose()`, so the close is
dead top-level code and ClaimQuests never closes the character window itself; the main loop's
following MainMenu() does. Reproduced as-is.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _claim_tab(g: Game, tab: atlas.Point) -> None:
    g.move_to(tab)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    if g.found(atlas.QUESTS_CLAIM_READY):
        g.move_to(atlas.QUESTS_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        g.move_to(atlas.QUESTS_REWARD_OK)
        g.sleep(1000)
        g.click()
        g.sleep(1000)


def claim_quests(g: Game) -> None:
    # open character window
    g.move_to(atlas.CHARACTER_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # open quests tab
    g.move_to(atlas.QUESTS_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    _claim_tab(g, atlas.QUESTS_DAILY_TAB)
    _claim_tab(g, atlas.QUESTS_WEEKLY_TAB)
