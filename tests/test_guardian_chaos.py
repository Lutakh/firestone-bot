"""Guardian chaos tab: opened on a roster bell too, preferred guardian first, then the others.

The fake models what was measured on the owner's game (2026-09-24): a roster bell shows on
every guardian that can afford an upgrade, the tab bell only when the guardian on display
can, and the Upgrade button is green when the displayed guardian can afford it.
"""

import pytest

from firestone_bot.features import guardian_chaos
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas

PORTRAITS = {p: i for i, (_, p) in enumerate(atlas.GUARDIAN_ROSTER, start=1)}
BELLS = {b.name: i for i, (b, _) in enumerate(atlas.GUARDIAN_ROSTER, start=1)}


@pytest.fixture(autouse=True)
def _no_patience(monkeypatch):
    monkeypatch.setattr(guardian_chaos, "BUTTON_BACK_MS", 0)  # the fake's sleep takes no time


class FakeGame:
    def __init__(self, currency, costs, displayed=1, order="1,2,3,4"):
        self.settings = Settings()
        self.settings.set("ChaosGuardianOrder", order)
        self.currency = currency
        self.costs = dict(costs)
        self.displayed = displayed
        self.tab = "training"
        self.pointer = None
        self.bought: list[int] = []
        self.taps: list = []
        self.lines: list[str] = []

    def affordable(self, i):
        return i in self.costs and self.currency >= self.costs[i]

    def found(self, probe):
        if probe is atlas.GUARDIAN_CHAOS_TAB_BELL:
            return self.affordable(self.displayed)
        if probe.name in BELLS:
            return self.affordable(BELLS[probe.name])
        if probe is atlas.GUARDIAN_CHAOS_UPGRADE_READY:
            hovered = self.pointer == atlas.GUARDIAN_CHAOS_UPGRADE
            return self.tab == "chaos" and self.affordable(self.displayed) and not hovered
        raise AssertionError(f"unexpected probe {probe.name}")

    def tap(self, point, settle_ms=1500, expect=None):
        self.taps.append(point)
        self.pointer = point
        if point is atlas.GUARDIAN_CHAOS_TAB:
            self.tab = "chaos"
        elif point is atlas.GUARDIAN_BACK_TAB:
            self.tab = "training"
        elif point in PORTRAITS:
            self.displayed = PORTRAITS[point]
        elif point is atlas.GUARDIAN_CHAOS_UPGRADE:
            assert self.tab == "chaos" and self.affordable(self.displayed)
            self.currency -= self.costs[self.displayed]
            self.costs[self.displayed] += 1000
            self.bought.append(self.displayed)

    def move_to(self, point):
        self.pointer = point

    def sleep(self, ms):
        pass

    def wait_still(self):
        pass

    def status(self, text):
        self.lines.append(text)


def test_displayed_guardian_too_expensive_the_others_are_still_upgraded():
    """The owner's case: guardian 3 (first choice, on display after training) costs more
    than the currency, the tab has no bell, 1, 2 and 4 have one."""
    g = FakeGame(33651, {1: 20394, 2: 20000, 3: 54218, 4: 21000}, displayed=3, order="3,1,2,4")
    assert not g.found(atlas.GUARDIAN_CHAOS_TAB_BELL)
    assert guardian_chaos.upgrade_on_guardian_screen(g) == 1
    assert g.bought == [1]
    assert g.tab == "training"  # back on the first tab for the training probes


def test_preferred_guardian_first_while_affordable_then_the_others():
    g = FakeGame(14000, {1: 2500, 2: 2000, 3: 4000, 4: 9000}, order="3,1,2,4")
    guardian_chaos.upgrade_on_guardian_screen(g)
    # 3 at 4000 then 5000 (5000 left, next 6000); 1 at 2500 (2500 left); 2 at 2000; 4 never
    assert g.bought == [3, 3, 1, 2]


def test_no_bell_anywhere_opens_nothing():
    g = FakeGame(100, {1: 3000, 2: 2000, 3: 1500, 4: 5000})
    assert guardian_chaos.upgrade_on_guardian_screen(g) == 0
    assert g.taps == []


def test_guardian_without_a_bell_is_never_tapped():
    """A locked or unowned slot has no bell: its portrait is not clicked (a locked panel
    could hold a green button that is not an Upgrade)."""
    g = FakeGame(5000, {1: 3000}, order="4,3,2,1")
    guardian_chaos.upgrade_on_guardian_screen(g)
    assert g.bought == [1]
    tapped = [PORTRAITS[p] for p in g.taps if p in PORTRAITS]
    assert tapped == [1]


def test_order_parsing_ignores_junk_and_duplicates():
    g = FakeGame(0, {})
    g.settings.set("ChaosGuardianOrder", "2; 2, x, 5, 4")
    assert guardian_chaos.guardian_order(g) == [2, 4]
    g.settings.set("ChaosGuardianOrder", "")
    assert guardian_chaos.guardian_order(g) == [1, 2, 3, 4]


def test_trip_after_the_chaos_hits_needs_the_town(monkeypatch):
    """A panel left open swallows the T: its own X would pass for the guardian screen."""
    g = FakeGame(33651, {1: 20394})
    monkeypatch.setattr(guardian_chaos, "town_is_open", lambda game: False)
    monkeypatch.setattr(guardian_chaos, "open_town", lambda game: False)
    with pytest.raises(guardian_chaos.ScreenNotReached):
        guardian_chaos.upgrade_after_chaos(g)
    assert g.taps == []
