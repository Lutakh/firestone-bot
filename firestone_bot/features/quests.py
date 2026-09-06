"""Port of Functions/Quests.ahk: claim daily and weekly quest rewards.

NOTE: in the AHK file the function's closing brace comes BEFORE `BigClose()`, so the close is
dead top-level code and ClaimQuests never closes the character window itself; the main loop's
following MainMenu() does. Reproduced as-is.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _claim_tab(g: Game, tab: atlas.Point) -> None:
    g.tap(tab, 1000)
    if g.found(atlas.QUESTS_CLAIM_READY):
        g.tap(atlas.QUESTS_CLAIM, 1000)
        g.tap(atlas.QUESTS_REWARD_OK, 1000)


def claim_quests(g: Game) -> None:
    if not g.found(g.ms.quests_badge):
        g.status("Quests: no notification badge, nothing to claim")
        return
    # open character window
    g.open_screen(g.ms.character_icon, g.ms.character_close_x, 1000)
    # open quests tab
    g.tap(atlas.QUESTS_TAB, 1000)
    _claim_tab(g, atlas.QUESTS_DAILY_TAB)
    _claim_tab(g, atlas.QUESTS_WEEKLY_TAB)
