"""Port of Functions/subFunctions/MapClose.ahk: close a map mission pop-up."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision.atlas import MAP_POPUP_CLOSE


def map_close(g: Game) -> None:
    g.focus()
    g.tap(MAP_POPUP_CLOSE)
