"""Chaos rift shop: buy the "Tome of power" books once a day (owner request 2026-09-04).

From the rift screen: the Shop button (right column) shows a bell when something is available;
inside, the left menu has "Monthly pass" and "Supplies" (bell on Supplies); the Supplies page
shows the book card with a green price button that stays green while affordable (the price
rises after each purchase, and the button turns lighter green 0x16BC15 while hovered, so the
mouse is moved away before each probe). No confirmation pop-up; when the runes run out the
button is STILL green and the click opens a "You need N more Dark rune" pop-up with an OK
button, which is the stop signal (measured live).
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas

MAX_BOOKS_PER_VISIT = 60


def buy_books(g: Game) -> int:
    """Rift screen must be open. Returns the number of books bought; leaves the rift open."""
    if not g.found(atlas.RIFT_SHOP_BELL):
        g.status("Chaos rift shop: no notification, nothing to buy")
        return 0
    g.tap(atlas.RIFT_SHOP, 2000)
    # Fast timing returned as soon as the shop started to draw and the bell probe missed
    # (2026-09-08: "Supplies has no notification", shop closed at once). Wait for the
    # bell with patience; without it, still look at the Supplies page: the book button
    # decides.
    g.wait_still()
    if not g.wait_for(atlas.RIFT_SUPPLIES_BELL, 3000):
        g.status("Chaos rift shop: Supplies shows no notification, checking the page anyway")
    g.tap(atlas.RIFT_SUPPLIES, 2000)
    g.wait_still()
    bought = 0
    while bought < MAX_BOOKS_PER_VISIT:
        g.move_to(atlas.RIFT_BOOKS_PARK)  # hover would turn the button lighter green
        g.sleep(500)
        if not g.wait_for(atlas.RIFT_BOOKS_READY, 2500 if bought else 4000):
            break
        g.tap(atlas.RIFT_BOOKS_BUY, 0)
        g.sleep(500)  # let Unity process the click before the pointer leaves the button
        g.move_to(atlas.RIFT_BOOKS_PARK)
        g.sleep(1500)
        if g.found(atlas.RIFT_NEED_MORE_OK_READY):
            # not enough runes: dismiss the pop-up and stop
            g.move_to(atlas.RIFT_NEED_MORE_OK)
            g.sleep(800)
            g.click()
            g.sleep(1000)
            break
        bought += 1
    g.status(f"Chaos rift shop: {bought} book(s) bought")
    big_close(g)  # shop -> rift screen
    return bought
