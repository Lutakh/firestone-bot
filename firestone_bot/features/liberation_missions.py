"""Port of Functions/subFunctions/LiberationMissions.ahk + LiberationInProgressCheck.ahk.

Reached from ClaimCampaign.ahk when the Liberation setting is on.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def liberation_in_progress(g: Game) -> bool:
    cap = int(g.settings.get("SafetyCap") or 0)
    n = 0
    while True:  # Search:
        if g.found(atlas.LIB_DONE):
            g.move_to(atlas.LIB_DONE_CLAIM)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
            return True
        g.sleep(2000)
        g.move_to(atlas.LIB_HOVER)
        n += 1
        if cap and n >= cap:
            g.status(f"LiberationInProgress: safety cap of {cap} iterations reached")
            return True


def _mission(g: Game, point: atlas.Point) -> bool:
    """Click a mission; True when it was already done (orange marker), else run it."""
    g.move_to(point)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    if g.found(atlas.LIB_ALREADY_DONE):
        return True
    while not liberation_in_progress(g):
        g.sleep(5000)
    return False


def liberation_missions(g: Game) -> None:
    g.focus()
    # open daily missions if notification present
    if not g.found(atlas.LIB_DOT):
        return
    g.move_to(atlas.LIB_OPEN)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # open Liberation
    g.move_to(atlas.LIB_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    g.wheel(-70)
    for point in atlas.LIB_MISSIONS_PAGE2:  # 319, 190, 155, 110, 80 stars
        _mission(g, point)
    g.wheel(63)
    for point in atlas.LIB_MISSIONS_PAGE1:  # 60, 40, 20, 10, 5 stars
        _mission(g, point)
    big_close(g)
    # CheckDungeon:
    if g.settings.flag("DungeonQuest"):
        g.move_to(atlas.LIB_DUNGEON)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        _mission(g, atlas.LIB_DUNGEON_120)
        if _mission(g, atlas.LIB_DUNGEON_70):
            return  # AHK returns without the closing BigCloses
    big_close(g)
    big_close(g)
