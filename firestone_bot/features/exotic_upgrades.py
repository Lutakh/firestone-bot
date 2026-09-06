"""Port of Functions/subFunctions/ExoticUpgrades.ahk: buy the first affordable upgrade in a
4-row grid, scrolling between rows. Returns after the first purchase."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def exotic_upgrades(g: Game) -> None:
    g.tap(atlas.EXOTIC_UPGRADES_TAB, 1000)
    g.move_to(atlas.EXOTIC_UPGRADES_HOVER)
    for scroll, row in atlas.EXOTIC_UPGRADE_ROWS:
        if scroll:
            g.wheel(-scroll)
        for probe, button in row:
            if g.found(probe):
                g.tap(button, 500)
                return
