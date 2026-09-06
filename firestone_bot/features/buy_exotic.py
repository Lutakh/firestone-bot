"""Port of Functions/subFunctions/BuyExotic.ahk: buy gear / war machine / oracle chests in the
emblem market when affordable."""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def buy_exotic(g: Game) -> None:
    # open emblem market
    g.tap(atlas.EMBLEM_MARKET_TAB, 1000)
    for tab in atlas.EMBLEM_CHEST_TABS:
        g.tap(tab, 1000)
        # attempt to buy
        if g.found(atlas.EMBLEM_BUY_READY):
            g.tap(atlas.EMBLEM_BUY, 1000)
