"""Port of Functions/ExoticMerchant.ahk: sell exotic items, then upgrades and chest purchases."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.buy_exotic import buy_exotic
from firestone_bot.features.exotic_upgrades import exotic_upgrades
from firestone_bot.game import Game
from firestone_bot.vision import atlas

MAX_SELLS_PER_ITEM = 60


def _sell(g: Game, items) -> None:
    """Sell every copy of each item: click while its button stays green (AHK sold one per
    visit, owner 2026-09-08). The pointer is parked between clicks: a hovered button is a
    lighter green and the probe would miss it."""
    for probe, button in items:
        sold = 0
        while sold < MAX_SELLS_PER_ITEM:
            g.move_to(atlas.EXOTIC_PARK)
            g.sleep(300)
            if not g.found(probe):
                break
            g.tap(button, 800)
            g.wait_still()
            sold += 1
        if sold:
            g.status(f"Exotic merchant: {probe.name} sold {sold} time(s)")


def wants_visit(g: Game) -> bool:
    """Selling needs something to sell: a chest opened this cycle (Game.vars). The upgrade
    and chest purchases justify the visit on their own."""
    s = g.settings
    sells = s.flag("SellScrolls") or s.flag("SellAll") or s.flag("SellNoGold")
    if sells and g.vars.get("chests_opened", 0):
        return True
    if s.flag("ExoticUpgrades") or s.flag("BuyEx"):
        return True
    g.status("Exotic merchant: no chest opened this cycle, nothing to sell, visit skipped")
    return False


def exotic_merchant(g: Game) -> None:
    # Open exotic merchant
    g.tap(atlas.TOWN_EXOTIC_MERCHANT, expect=atlas.DIALOG_CLOSE_X)
    s = g.settings
    sells = s.flag("SellScrolls") or s.flag("SellAll") or s.flag("SellNoGold")
    if sells and g.vars.get("chests_opened", 0):
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
    if s.flag("BuyEx") and not g.locked("emblem_chests"):
        buy_exotic(g)
    big_close(g)
