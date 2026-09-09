"""Port of Functions/subFunctions/OpenTown.ahk: hotkey T opens the town.

The town screen is the base of a whole section of the cycle and every building is clicked by
position on it, so when T does not open it (the game busy with an animation - a new war
machine being handed out, owner 2026-09-09 - or the keyboard gone to another window) those
clicks land on whatever else is on screen: that run walked into the settings window and its
"Patch notes" button while it believed it was in the tavern. `open_town` now reports whether
the town is really there, and `town_is_open` re-checks it before each town step so the runner
skips the step instead of clicking blind.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def town_is_open(g: Game) -> bool:
    """Whether the town screen is on display right now (one capture, no click, no wait)."""
    return g.found(atlas.TOWN_OPEN)


def open_town(g: Game) -> bool:
    """Open the town with T. Returns whether the town screen is there afterwards (always
    True in safe timing, which cannot tell)."""
    g.focus()
    g.toast("Open Town", "Opening the Town Window", 1.5)
    g.key("t")
    if not g.fast():
        g.sleep(1500)
        return True
    g.sleep(g.CHANGE_SETTLE_MS)
    if not g.wait_for(atlas.TOWN_OPEN):
        # the key may have gone to another window (first cycle after the bot window was
        # raised): a click on the battlefield gives the game the keyboard, then T again
        g.save_diagnostic("town-miss.png")
        if g.found(atlas.MM_SETTINGS_OPEN) or g.found(atlas.DIALOG_CLOSE_X):
            # a dialog swallowed the T: the neutral spot of the battlefield is inside it
            # here (the settings window, with its "Switch server" button, 2026-09-09), so
            # nothing is clicked and the caller is told to clear the screen first
            g.status("Open Town: a dialog is in the way of the town, not clicking blind")
            return False
        g.status("Open Town: the town did not appear after T, clicking the game and retrying")
        g.focus()
        g.tap(atlas.GAME_NEUTRAL_SPOT, 300)
        g.key("t")
        g.sleep(g.CHANGE_SETTLE_MS)
        if not g.wait_for(atlas.TOWN_OPEN):
            g.status("Open Town: still no town after the second T")
            g.save_diagnostic("town-miss2.png")
            return False
    g.wait_still()  # the town scales in after its X shows: let it settle before clicking
    g.save_diagnostic("town-open.png")  # what the town section starts from (2026-09-07)
    return True
