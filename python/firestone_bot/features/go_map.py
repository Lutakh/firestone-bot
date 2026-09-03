"""Port of Functions/subFunctions/GoMap.ahk: hotkey M opens the map."""

from __future__ import annotations

from firestone_bot.game import Game


def go_map(g: Game) -> None:
    g.focus()
    g.toast("Open Map", "Opening the map window", 1.5)
    g.key("m")
    g.sleep(1500)
