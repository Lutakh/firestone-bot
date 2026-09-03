"""Port of Functions/UpgradeBlessings.ahk + subFunctions/ClickBless.ahk.

Twelve clock positions plus the "fate" centre, each with a red-dot probe and a click point.
AHK typo fixed: the 9 o'clock rect had y2 = 5541 (plan 1.2); 554 is used here.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def click_bless(g: Game) -> None:
    for _ in range(5):
        if g.found(atlas.BLESS_UPGRADE_READY):
            g.move_to(atlas.BLESS_UPGRADE)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
    g.move_to(atlas.BLESS_CLOSE)
    g.sleep(1000)
    g.click()
    g.sleep(1000)


def upgrade_blessings(g: Game) -> None:
    # open blessings page if ready
    if not g.found(atlas.BLESSINGS_DOT):
        return
    g.move_to(atlas.BLESSINGS_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    for probe, button in atlas.BLESSING_SLOTS:
        if g.found(probe):
            g.move_to(button)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
            click_bless(g)
