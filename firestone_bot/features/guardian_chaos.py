"""Guardian "Chaos rift" tab upgrades (Python-only feature, owner request 2026-09-04).

Chaos rift hits send a holy-damage currency by mail; it is spent on the third tab of the
guardian screen (Magic Quarter). The user chooses the order with the `ChaosGuardianOrder`
setting ("3,1,2,4" = roster positions): the first guardian is upgraded while its green
"Upgrade" button stays green, then each of the others that can still afford one.

What the bells mean (measured 2026-09-24 on the owner's game, 33,651 currency; guardian 3
cost 54,218, guardians 1, 2 and 4 about 20,000):
- a red bell on a roster portrait: that guardian can afford an upgrade (bells on 1, 2, 4;
  none on 3), the same on every tab of the screen;
- the bell on the chaos tab itself: the guardian ON DISPLAY can afford one. With guardian
  3 displayed the tab had no bell, with 1, 2 or 4 displayed it had one.
The bot used to open the tab only on the tab bell. Training leaves the GuardianTrain
guardian on display, often the preferred and most expensive one, so its bell stayed off and
the others were never upgraded while their bells showed (owner, 2026-09-24: 33,651 unspent
for a day). The tab is now opened when the tab bell OR any roster bell shows.

Called (1) from guardian() every cycle, and (2) right after the chaos rift hits of the day
(runner, via Game.vars["chaos_hits"]).
"""

from __future__ import annotations

import time

from firestone_bot.features.big_close import big_close
from firestone_bot.features.open_town import open_town, town_is_open
from firestone_bot.game import Game, ScreenNotReached
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


def roster_bells(g: Game) -> list[int]:
    """Roster positions (1..4) whose portrait shows a red bell."""
    return [i for i, (bell, _) in enumerate(atlas.GUARDIAN_ROSTER, start=1) if g.found(bell)]


def upgrade_on_guardian_screen(g: Game) -> int:
    """Guardian screen must be open. Returns the number of upgrades bought."""
    tab_bell = g.found(atlas.GUARDIAN_CHAOS_TAB_BELL)
    if not tab_bell and not roster_bells(g):
        return 0
    g.tap(atlas.GUARDIAN_CHAOS_TAB)
    g.wait_still()
    g.move_to(atlas.GUARDIAN_CHAOS_PARK)
    g.sleep(300)
    bells = roster_bells(g)
    total = 0
    for idx in guardian_order(g):
        bell, portrait = atlas.GUARDIAN_ROSTER[idx - 1]
        if not g.found(bell):  # read again: the purchases before can take it away
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
    if not total:
        g.status(
            f"Guardian chaos tab: bells on {bells or 'no guardian'}, nothing bought"
            + ("" if tab_bell else " (no bell on the tab)")
        )
    # back to the first tab, where the training probes of guardian() live
    g.tap(atlas.GUARDIAN_BACK_TAB, 1000)
    return total


def upgrade_after_chaos(g: Game) -> None:
    """From the main screen: open town > Magic Quarter, upgrade, back to the main screen."""
    if not town_is_open(g) and not open_town(g):
        # a panel left open swallowed the T: its own X would pass for the guardian screen's
        raise ScreenNotReached("town")
    g.require_screen(atlas.TOWN_MAGIC_QUARTER, atlas.DIALOG_CLOSE_X, 6500, via_town=True)
    g.sleep(1000)  # its content draws after the X (as in guardian())
    if not town_is_open(g):
        upgrade_on_guardian_screen(g)
    big_close(g)  # guardian screen -> town
    big_close(g)  # town -> main screen
