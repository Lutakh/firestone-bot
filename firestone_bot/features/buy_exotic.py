"""Port of Functions/subFunctions/BuyExotic.ahk: buy gear / war machine / oracle chests in the
emblem market when affordable."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def buy_exotic(g: Game) -> None:
    # open emblem market
    g.move_to(atlas.EMBLEM_MARKET_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    for tab in atlas.EMBLEM_CHEST_TABS:
        g.move_to(tab)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        # attempt to buy
        if g.found(atlas.EMBLEM_BUY_READY):
            g.move_to(atlas.EMBLEM_BUY)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
