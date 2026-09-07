"""Port of Functions/subFunctions/BigClose.ahk: click the big X that closes menus."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import BIG_CLOSE


def big_close(g: Game) -> None:
    # New adventure style: the settings gear sits where the X of a dialog would be, so a
    # BigClose on the main screen would open Options (keys are ignored while it is up).
    if g.style == "new" and g.found(atlas.NS_STYLE_PROBE):
        g.status("BigClose: already on the main screen, nothing to close")
        return
    g.tap(BIG_CLOSE)
