"""Daily missions of the campaign screen: Liberation areas and Dungeons.

Rework of subFunctions/LiberationMissions.ahk. The AHK bot wheeled the card row to one end,
clicked five fixed card positions, wheeled to the other end and clicked five more, waiting on
each one; a card in the middle of the row was never reached (Ixyon, 2026-09-09: "it does not
click on Xandor's liberation mission") and a screen where everything was already done was
still walked through card by card (owner, 2026-09-09: the bot looped on the daily missions
with nothing to claim).

Here the row is scrolled from one end to the other and only the cards showing a green button
are clicked: a card that is finished says "Area has been liberated" / "Dungeon has been
cleared" with no button at all (measured live, 2026-09-09: zero green pixels in the whole
card area), so the green button is both the "there is something to do" test and the target.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells
from firestone_bot.vision.buttons import green_buttons

MAX_MISSIONS = 12  # safety: hard stop on the number of missions started in one visit
MAX_SCROLL_STEPS = 14  # safety: hard stop on the number of wheel steps across the row
MISSION_CHECKS = 20  # how many times a running mission is looked at (2 s apart)


def liberation_in_progress(g: Game) -> bool:
    """True once the running mission's green Claim button was found and clicked (or the
    check budget ran out): the mission plays a short battle before the reward shows."""
    for _ in range(MISSION_CHECKS):
        if g.found(atlas.LIB_DONE):
            g.tap(atlas.LIB_DONE_CLAIM, 1000)
            return True
        g.move_to(atlas.LIB_HOVER)
        g.sleep(2000)
    g.status("Daily missions: the mission did not finish in time, leaving it running")
    return False


def _row_image(g: Game) -> np.ndarray:
    return g.region_image(atlas.LIB_CARD_AREA).astype(int)


def _scrolled(g: Game, notches: int) -> bool:
    """Wheel the card row and say whether it actually moved (False = end of the row)."""
    before = _row_image(g)
    g.move_to(atlas.LIB_ROW_HOVER)
    g.sleep(200)
    g.wheel(notches)
    g.sleep(700)
    after = _row_image(g)
    if after.shape != before.shape:
        return True
    return float(np.abs(after - before).mean()) > 2.0


def _play_mission(g: Game, name: str) -> None:
    """A card's green button was clicked: let the mission play, claim its reward, and come
    back to the card row."""
    g.wait_still()
    g.save_diagnostic(f"{name.lower()}-mission.png")  # what the game shows, for tuning
    liberation_in_progress(g)
    # back to the card row when the mission opened a screen of its own
    if not green_buttons(g, atlas.LIB_CARD_AREA) and g.found(atlas.DIALOG_CLOSE_X):
        big_close(g)
        g.wait_still()


def _run_screen(g: Game, open_button: atlas.Point, name: str) -> int:
    """Open one daily-mission screen and start every mission that offers a green button."""
    g.tap(open_button, 1200)
    g.wait_still()
    started = 0
    _scrolled(g, atlas.LIB_SCROLL_TO_START)  # back to the first card
    for _ in range(MAX_SCROLL_STEPS):
        while started < MAX_MISSIONS:
            buttons = green_buttons(g, atlas.LIB_CARD_AREA)
            if not buttons:
                break
            g.status(f"{name}: a mission is available, starting it")
            g.tap(buttons[0], 1200)
            _play_mission(g, name)
            started += 1
        if started >= MAX_MISSIONS or not _scrolled(g, -atlas.LIB_SCROLL_STEP):
            break
    if not started:
        g.status(f"{name}: nothing to start, every mission is already done")
    big_close(g)
    g.wait_still()
    return started


def liberation_missions(g: Game) -> None:
    """From the campaign screen: open Daily missions when its bell shows, then Liberation
    and (when enabled) Dungeon."""
    g.focus()
    if not bells.bell_in(g, atlas.LIB_DOT):
        g.status("Daily missions: no bell, nothing to do")
        return
    g.tap(atlas.LIB_OPEN, 1200)
    g.wait_still()
    _run_screen(g, atlas.LIB_TAB, "Liberation")
    if g.settings.flag("DungeonQuest"):
        _run_screen(g, atlas.LIB_DUNGEON, "Dungeon")
    big_close(g)
