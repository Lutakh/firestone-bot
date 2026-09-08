"""Guardian "Chaos rift" tab upgrades (Python-only feature, owner request 2026-09-04).

Chaos rift hits send a holy-damage currency by mail; it is spent on the third tab of the
guardian screen (Magic Quarter). A bell on a guardian's portrait (bottom roster) means that
guardian can be upgraded there. The user chooses the order with the `ChaosGuardianOrder`
setting ("3,1,2,4" = roster positions); each guardian in that order is upgraded while its
green "Upgrade" button stays green, then the next one with a bell is tried.

Called (1) from guardian() every cycle, when the tab-3 bell shows, and (2) right after the
chaos rift hits of the day (runner, via Game.vars["chaos_hits"]).
"""

from __future__ import annotations

import time

from firestone_bot.features.big_close import big_close
from firestone_bot.features.open_town import open_town
from firestone_bot.game import Game
from firestone_bot.vision import atlas

MAX_UPGRADES_PER_GUARDIAN = 50  # safety: the button greys out when the currency runs out
BUTTON_BACK_MS = 3000  # patience for the Upgrade button to be green again after a click


def _upgrade_ready(g: Game) -> bool:
    """The green Upgrade button, read with the pointer parked (hovered it is lighter green
    and the probe missed: one upgrade per guardian instead of all of them, 2026-09-08) and
    with patience: right after a click it is pressed / greyed for a moment."""
    g.move_to(atlas.GUARDIAN_CHAOS_PARK)
    g.sleep(300)
    end = time.monotonic() + BUTTON_BACK_MS / 1000
    while True:
        if g.found(atlas.GUARDIAN_CHAOS_UPGRADE_READY):
            return True
        if time.monotonic() >= end:
            return False
        g.sleep(250)


def guardian_order(g: Game) -> list[int]:
    order: list[int] = []
    for part in g.settings.get("ChaosGuardianOrder").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= 4 and int(part) not in order:
            order.append(int(part))
    return order or [1, 2, 3, 4]


def upgrade_on_guardian_screen(g: Game) -> int:
    """Guardian screen must be open. Returns the number of upgrades bought."""
    if not g.found(atlas.GUARDIAN_CHAOS_TAB_BELL):
        return 0
    g.tap(atlas.GUARDIAN_CHAOS_TAB)
    total = 0
    for idx in guardian_order(g):
        bell, portrait = atlas.GUARDIAN_ROSTER[idx - 1]
        if not g.found(bell):
            continue
        g.tap(portrait)
        bought = 0
        while bought < MAX_UPGRADES_PER_GUARDIAN and _upgrade_ready(g):
            g.tap(atlas.GUARDIAN_CHAOS_UPGRADE, 0)
            g.sleep(500)  # let Unity take the click before the pointer leaves the button
            bought += 1
        if bought:
            g.status(f"Guardian {idx}: {bought} chaos-rift upgrade(s)")
        else:
            g.status(f"Guardian {idx}: Upgrade button not green, next guardian")
        total += bought
    # back to the first tab, where the training probes of guardian() live
    g.tap(atlas.GUARDIAN_BACK_TAB, 1000)
    return total


def upgrade_after_chaos(g: Game) -> None:
    """From the main screen: open town > Magic Quarter, upgrade, back to the main screen."""
    open_town(g)
    g.tap(atlas.TOWN_MAGIC_QUARTER, 6500)
    upgrade_on_guardian_screen(g)
    big_close(g)  # guardian screen -> town
    big_close(g)  # town -> main screen
