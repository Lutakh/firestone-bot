"""Chaos rift: a hit counts only when the free moonstone counter drops (or, unreadable, when
the Hit button greys with the pointer parked), and the day ends with no free moonstone left.

The fake rift: a green Hit button with the free icon while free moonstones are left, drawn
lighter while the pointer is on it (the probe then misses, as on the game), grey during a
battle until the rift is reopened. Each tap is taken or ignored as scripted.
"""

import pytest

from firestone_bot.features import chaos, token_counter
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas


class FakeRift:
    def __init__(self, tmp_path, free, taken, max_chaos=10, count=0, readable=True, lag=False):
        self.settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        self.settings.set("MaxChaos", max_chaos)
        self.settings.set("ChaosCountDaily", count)
        self.settings.set("ChaosBooks", "0")
        self.free = free
        self.shown = free  # what the counter shows (lags until a reopen when `lag`)
        self.taken = list(taken)  # per tap: moonstones spent (0 = the game ignored the click)
        self.readable = readable
        self.lag = lag
        self.battle = False
        self.zero = False  # the counter reads 0 whatever the game holds
        self.pointer = None
        self.vars = {}
        self.taps = 0
        self.lines = []
        self.captures = []

    # the game
    def reopen(self):
        self.battle = False
        self.shown = self.free

    def found(self, probe):
        if probe is atlas.CHAOS_DOT:
            return True
        if probe is atlas.CHAOS_HIT_READY:
            return not self.battle and self.pointer is not atlas.CHAOS_HIT
        if probe is atlas.CHAOS_HIT_ICON_FREE:
            return self.free > 0
        if probe is atlas.CHAOS_HIT_ICON_PAID:
            return self.free == 0
        raise AssertionError(probe.name)

    def tap(self, point, settle_ms=1500, expect=None):
        self.pointer = point
        assert point is atlas.CHAOS_HIT
        assert self.free > 0, "a paid moonstone was spent"
        self.taps += 1
        spent = self.taken.pop(0) if self.taken else 1
        if spent:
            self.free -= spent
            self.battle = True
            if not self.lag:
                self.shown = self.free

    # Game API
    def focus(self):
        pass

    def move_to(self, point):
        self.pointer = point

    def sleep(self, ms):
        pass

    def wait_gone(self, probe, timeout_ms):
        return not self.found(probe)

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)


@pytest.fixture
def rift(monkeypatch, tmp_path):
    def make(**kw):
        g = FakeRift(tmp_path, **kw)
        monkeypatch.setattr(
            token_counter,
            "read",
            lambda game, rect: None if not game.readable else 0 if game.zero else game.shown,
        )
        monkeypatch.setattr(chaos, "_open_rift", lambda game: game.reopen())
        monkeypatch.setattr(chaos, "big_close", lambda game: None)
        monkeypatch.setattr(chaos.multiplier, "ensure_single", lambda game, screen: True)
        monkeypatch.setattr(chaos, "buy_books", lambda game: False)
        return g

    return make


def _count(g):
    return int(g.settings.get("ChaosCountDaily"))


def test_an_ignored_click_is_not_counted(rift):
    g = rift(free=3, taken=[1, 0, 1, 1], count=7)
    chaos.hit_chaos(g)
    assert _count(g) == 10
    assert g.free == 0
    assert g.taps == 4
    assert sum("spent no free moonstone" in s for s in g.lines) == 1


def test_counter_unreadable_the_button_is_read_with_the_pointer_parked(rift):
    """The old check read the button with the pointer on it: hovered, it never looked
    green, so an ignored click counted too."""
    g = rift(free=3, taken=[0, 1], count=9, readable=False)
    chaos.hit_chaos(g)
    assert g.taps == 2
    assert _count(g) == 10
    assert g.free == 2


def test_free_moonstones_left_at_the_limit_are_used(rift):
    """10 counted, one free moonstone left (a miscount, or yesterday's moonstone hit before
    the new ones came): with MaxChaos 10 the counter wins."""
    g = rift(free=2, taken=[1, 1], count=9)
    chaos.hit_chaos(g)
    assert g.free == 0
    assert _count(g) == 10
    assert any("free moonstone(s) left, using them" in s for s in g.lines)


def test_a_lower_limit_is_kept(rift):
    g = rift(free=6, taken=[1], max_chaos=5, count=4)
    chaos.hit_chaos(g)
    assert g.taps == 1
    assert g.free == 5


def test_a_hit_shown_late_is_confirmed_after_the_reopen(rift):
    g = rift(free=5, taken=[1], max_chaos=5, count=4, lag=True)
    chaos.hit_chaos(g)
    assert g.taps == 1
    assert _count(g) == 5
    assert any("confirmed late" in s for s in g.lines)


def test_a_click_that_spends_several_moonstones_stops_the_visit(rift):
    g = rift(free=10, taken=[5], count=0)
    chaos.hit_chaos(g)
    assert g.taps == 1
    assert _count(g) == 5
    assert any("multiplier is not x1" in s for s in g.lines)


def test_three_ignored_clicks_leave_and_keep_the_counter(rift):
    """The button stayed green: the game really ignored them, the counter was right."""
    g = rift(free=3, taken=[0, 0, 0], count=0)
    chaos.hit_chaos(g)
    assert g.taps == 3
    assert _count(g) == 0
    assert not g.vars.get(chaos.COUNTER_OFF)
    assert g.captures == ["chaos-hit-not-taken.png"]


def test_a_slow_counter_never_ends_the_visit_early(rift):
    """Every hit shows on the counter only after the reopen: all ten are made and counted,
    and the counter stays trusted."""
    g = rift(free=10, taken=[], count=0, lag=True)
    chaos.hit_chaos(g)
    assert g.taps == 10
    assert _count(g) == 10
    assert g.free == 0
    assert not g.vars.get(chaos.COUNTER_OFF)


def test_a_counter_that_never_moves_is_dropped_and_its_battles_counted(rift):
    """The rect reads a steady number that is not the free counter (another window shape):
    the battles start, the number never drops. After two such hits the Hit button decides,
    and the day's limit is still kept."""
    g = rift(free=10, taken=[], max_chaos=5, count=0)
    g.zero = False
    real_read = chaos.token_counter.read
    chaos.token_counter.read = lambda game, rect: 93  # the paid-medal counter beside it
    try:
        chaos.hit_chaos(g)
    finally:
        chaos.token_counter.read = real_read
    assert g.vars.get(chaos.COUNTER_OFF) == 1
    assert _count(g) == 5
    assert g.free == 5  # exactly the limit spent


def test_a_multi_spend_blocks_the_next_visits_until_x1(rift, monkeypatch):
    g = rift(free=7, taken=[5], max_chaos=7, count=0)
    monkeypatch.setattr(chaos.multiplier, "read_multiplier", lambda game: None)
    chaos.hit_chaos(g)
    assert g.taps == 1 and _count(g) == 5
    chaos.hit_chaos(g)  # the label is still unreadable: no click at x5 again
    assert g.taps == 1
    monkeypatch.setattr(chaos.multiplier, "read_multiplier", lambda game: 1)
    chaos.hit_chaos(g)  # the label reads x1 now
    assert g.taps == 3 and _count(g) == 7


def test_counter_at_zero_never_clicks(rift):
    g = rift(free=1, taken=[1], count=0)
    g.zero = True  # the counter reads 0 while the icon still says free
    chaos.hit_chaos(g)
    assert g.taps == 0
