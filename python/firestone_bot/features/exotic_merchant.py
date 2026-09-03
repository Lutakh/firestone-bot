"""Port of Functions/ExoticMerchant.ahk: sell exotic items, then upgrades and chest purchases."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.buy_exotic import buy_exotic
from firestone_bot.features.exotic_upgrades import exotic_upgrades
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _sell(g: Game, items) -> None:
    for probe, button in items:
        if g.found(probe):
            g.move_to(button)
            g.sleep(1000)
            g.click()
            g.sleep(1000)


def exotic_merchant(g: Game) -> None:
    # Open exotic merchant
    g.move_to(atlas.TOWN_EXOTIC_MERCHANT)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    s = g.settings
    if s.flag("SellScrolls") or s.flag("SellAll") or s.flag("SellNoGold"):
        # SellStart:
        _sell(g, atlas.EXOTIC_SCROLLS)
        if s.flag("SellAll"):
            _sell(g, atlas.EXOTIC_GOLD_TOP)
            # scroll to bottom
            g.wheel(-35)
            _sell(g, atlas.EXOTIC_GOLD_BOTTOM)
            _sell(g, atlas.EXOTIC_ITEMS_BOTTOM)
        elif s.flag("SellNoGold"):
            g.wheel(-35)
            _sell(g, atlas.EXOTIC_ITEMS_BOTTOM)
    # ExChecks:
    if s.flag("ExoticUpgrades"):
        exotic_upgrades(g)
    if s.flag("BuyEx"):
        buy_exotic(g)
    big_close(g)
