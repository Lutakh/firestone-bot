"""Port of Functions/subFunctions/BigClose.ahk: click the big X that closes menus."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision.atlas import BIG_CLOSE


def big_close(g: Game) -> None:
    g.tap(BIG_CLOSE)
