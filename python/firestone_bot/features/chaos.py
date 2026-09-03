"""Port of Functions/subFunctions/Chaos.ahk: chaos rift auto battle from the guild screen."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def hit_chaos(g: Game) -> None:
    g.focus()
    # Check for Chaos notification on guild screen
    if g.found(atlas.CHAOS_DOT):
        g.click_point(atlas.CHAOS_OPEN)  # MouseClick, Left, x, y, 1, 0
        g.sleep(1500)
        # Change to auto
        g.click_point(atlas.CHAOS_AUTO)
        g.sleep(10000)
        big_close(g)
