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
        if not g.wait_for(atlas.TOWN_OPEN):
            g.status("Open Town: the town did not appear after T, pressing it again")
            g.save_diagnostic("town-miss.png")
            g.focus()
            g.key("t")
            g.sleep(g.CHANGE_SETTLE_MS)
            if not g.wait_for(atlas.TOWN_OPEN):
                g.status("Open Town: still no town after the second T")
        g.wait_still()  # the town scales in after its X shows: let it settle before clicking
    else:
        g.sleep(1500)
