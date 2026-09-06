"""Port of Functions/subFunctions/GoMap.ahk: hotkey M opens the map."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def go_map(g: Game) -> None:
    g.focus()
    g.toast("Open Map", "Opening the map window", 1.5)
    g.key("m")
    if g.fast():
        g.sleep(g.CHANGE_SETTLE_MS)
        if not g.wait_for(atlas.DIALOG_CLOSE_X):
            g.status("Open Map: the map did not appear after M, pressing it again")
            g.key("m")
            g.sleep(g.CHANGE_SETTLE_MS)
            g.wait_for(atlas.DIALOG_CLOSE_X)
    else:
        g.sleep(1500)
