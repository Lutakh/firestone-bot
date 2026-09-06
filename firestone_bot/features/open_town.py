"""Port of Functions/subFunctions/OpenTown.ahk: hotkey T opens the town."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def open_town(g: Game) -> None:
    g.focus()
    g.toast("Open Town", "Opening the Town Window", 1.5)
    g.key("t")
    if g.fast():
        g.sleep(g.CHANGE_SETTLE_MS)
        if not g.wait_for(atlas.DIALOG_CLOSE_X):
            g.status("Open Town: the town did not appear after T, pressing it again")
            g.key("t")
            g.sleep(g.CHANGE_SETTLE_MS)
            g.wait_for(atlas.DIALOG_CLOSE_X)
    else:
        g.sleep(1500)
