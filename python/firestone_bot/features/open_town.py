"""Port of Functions/subFunctions/OpenTown.ahk: hotkey T opens the town."""

from __future__ import annotations

from firestone_bot.game import Game


def open_town(g: Game) -> None:
    g.focus()
    g.toast("Open Town", "Opening the Town Window", 1.5)
    g.key("t")
    g.sleep(1500)
