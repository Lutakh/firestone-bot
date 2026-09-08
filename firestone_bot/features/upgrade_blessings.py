"""Port of Functions/UpgradeBlessings.ahk + subFunctions/ClickBless.ahk.

Twelve clock positions plus the "fate" centre, each with a red-dot probe and a click point.
AHK typo fixed: the 9 o'clock rect had y2 = 5541 (plan 1.2); 554 is used here.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells


def red_bell(g: Game, probe) -> bool:
    """A red bell inside the probe rect (vision/bells): the AHK exact colour missed the
    Blessings bell (0xF40000 for 0xF41000, variation 1) and the blessings were never
    upgraded (2026-09-08)."""
    return bells.has_bell(g, (probe.x1, probe.y1, probe.x2, probe.y2))


MAX_BLESS_UPGRADES = 60


def click_bless(g: Game) -> None:
    """Upgrade while the button stays green (AHK: five reads). The pointer is parked between
    clicks: a hovered button is a lighter green and the probe would miss it."""
    bought = 0
    while bought < MAX_BLESS_UPGRADES:
        g.move_to(atlas.BLESS_PARK)
        g.sleep(300)
        if not g.wait_for(atlas.BLESS_UPGRADE_READY, 2000 if bought else 3000):
            break
        g.tap(atlas.BLESS_UPGRADE, 800)
        bought += 1
    if bought:
        g.status(f"Blessings: {bought} upgrade(s) bought")
    g.tap(atlas.BLESS_CLOSE, 1000)


def upgrade_blessings(g: Game) -> None:
    # open blessings page if ready
    if not red_bell(g, atlas.BLESSINGS_DOT):
        g.status("Blessings: no notification bell, nothing to upgrade")
        return
    g.tap(atlas.BLESSINGS_TAB, 1000)
    g.wait_still()
    for probe, button in atlas.BLESSING_SLOTS:
        if red_bell(g, probe):
            g.status(f"Blessings: {probe.name} has a bell, upgrading")
            g.tap(button, 1000)
            click_bless(g)
