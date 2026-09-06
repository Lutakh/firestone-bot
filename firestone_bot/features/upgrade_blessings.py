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
            g.tap(atlas.BLESS_UPGRADE, 1000)
    g.tap(atlas.BLESS_CLOSE, 1000)


def upgrade_blessings(g: Game) -> None:
    # open blessings page if ready
    if not g.found(atlas.BLESSINGS_DOT):
        return
    g.tap(atlas.BLESSINGS_TAB)
    for probe, button in atlas.BLESSING_SLOTS:
        if g.found(probe):
            g.tap(button, 1000)
            click_bless(g)
