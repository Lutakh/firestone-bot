"""Guardian enlightenment: the Decorated Heroes event's 3 at x1, the automation's budget spent
with the screen's multipliers within a count, a dust cap and a reserve, every click counted
by the dust counter, the user's multiplier put back, the trips to the screen saved."""

from pathlib import Path

import numpy as np
import pytest

from firestone_bot import daily
from firestone_bot.features import enlighten, guardian, token_counter
from firestone_bot.game import BotStopped
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas
from firestone_bot.vision.digits import DigitReader

FIX = Path(__file__).parent / "fixtures"


def _settings(tmp_path, **values):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    for k, v in values.items():
        s.set(k, v)
    return s


# -- the button's cost -----------------------------------------------------------------------


class Crop:
    """region_image returns a capture of the cost rect (measured 2026-09-28, 1920x1009)."""

    def __init__(self, img):
        self.img = img
        self.reader = DigitReader()

    def region_image(self, rect, anchor=None):
        assert rect == atlas.GUARDIAN_ENLIGHTEN_COST and anchor is None
        return self.img

    def digit_reader(self):
        return self.reader


@pytest.mark.parametrize("cost", [20, 100, 200, 400])
def test_the_button_cost_reads_on_real_captures(cost):
    """x1, x5, x10, x20: "Enlightenment N / cost", white digits on the green button."""
    img = np.load(FIX / f"guardian-enlighten-cost-{cost}.npy")
    assert enlighten.button_cost(Crop(img)) == cost
    # a dialog dimming the screen never passes for another cost
    dimmed = (img.astype(np.float32) * 0.5).astype(np.uint8)
    assert enlighten.button_cost(Crop(dimmed)) is None


def test_the_plan_uses_the_largest_multipliers_first():
    assert enlighten.plan_clicks(425) == {20: 21, 5: 1}
    assert enlighten.plan_clicks(7) == {5: 1, 1: 2}
    assert enlighten.plan_clicks(397) == {20: 19, 10: 1, 5: 1, 1: 2}
    assert enlighten.plan_clicks(3) == {1: 3}
    assert enlighten.plan_clicks(0) == {}


# -- the guardian screen ---------------------------------------------------------------------


class FakeGuardian:
    """Guardian screen, first tab: multiplier cycle x20 -> x1 -> x5 -> x10 -> x20; one click
    buys `mult` enlightenments for 20 x mult strange dust while the dust covers it; the button
    is green then (not while hovered) and shows its cost; the dust counter reads the dust."""

    CYCLE = (20, 1, 5, 10)

    def __init__(
        self,
        settings,
        dust=8015,
        mult=20,
        taken=True,
        mult_readable=True,
        label=None,
        dust_readable=True,
        cost_readable=True,
        wrong_cost=None,
        blind_reads=0,
    ):
        self.settings = settings
        self.vars = {}
        self.dust = dust
        self.mult = mult
        self.taken = taken
        self.mult_readable = mult_readable
        self.label = label  # the label reads this whatever the screen holds
        self.dust_readable = dust_readable
        self.blind_reads = blind_reads  # the first counter reads fail (a redraw), then it reads
        self.cost_readable = cost_readable
        self.wrong_cost = wrong_cost or {}  # multiplier -> the cost shown instead
        self.pointer = None
        self.displayed = None
        self.enlightened = 0
        self.clicks = []  # the true multiplier of every Enlightenment click
        self.mult_taps = 0
        self.taps = []
        self.probes = []
        self.opened = False
        self.focused = False
        self.lines = []
        self.captures = []

    # what the bot reads
    def read_label(self):
        if not self.mult_readable:
            return None
        return self.mult if self.label is None else self.label

    def read_dust(self):
        if self.blind_reads:
            self.blind_reads -= 1
            return None
        return self.dust if self.dust_readable else None

    def read_cost(self):
        if not self.cost_readable:
            return None
        return self.wrong_cost.get(self.mult, 20 * self.mult)

    def found(self, probe):
        self.probes.append(probe)
        if probe is atlas.GUARDIAN_ENLIGHTEN_READY:
            hovered = self.pointer == atlas.GUARDIAN_ENLIGHTEN
            return self.dust >= 20 * self.mult and not hovered
        assert probe in (atlas.GUARDIAN_EVOLVE_DOT, atlas.GUARDIAN_TRAIN_READY), probe
        return False

    # what the bot does
    def tap(self, point, settle_ms=1500, expect=None):
        self.pointer = point
        self.taps.append(point)
        if point == atlas.GUARDIAN_MULTIPLIER:
            self.mult_taps += 1
            self.mult = self.CYCLE[(self.CYCLE.index(self.mult) + 1) % len(self.CYCLE)]
        elif point == atlas.GUARDIAN_ENLIGHTEN:
            self.clicks.append(self.mult)
            if self.taken and self.dust >= 20 * self.mult:
                self.dust -= 20 * self.mult
                self.enlightened += self.mult
        else:
            for i, (_, portrait) in enumerate(atlas.GUARDIAN_ROSTER, start=1):
                if point == portrait:
                    self.displayed = i

    def move_to(self, point):
        self.pointer = point

    def sleep(self, ms):
        pass

    def wait_still(self):
        pass

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)

    # guardian(): the way to the screen
    def focus(self):
        self.focused = True

    def fast(self):
        return True

    def require_screen(self, point, expect, settle_ms=1500, via_town=False):
        assert point == atlas.TOWN_MAGIC_QUARTER
        self.opened = True


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(enlighten, "monotonic", c)
    return c


@pytest.fixture
def screen(monkeypatch, tmp_path, clock):
    def make(settings=None, **kw):
        s = _settings(tmp_path, GuardianTrain="3", **(settings or {}))
        g = FakeGuardian(s, **kw)
        monkeypatch.setattr(
            enlighten.multiplier, "read_multiplier", lambda game, rect, anchor: game.read_label()
        )

        def read(game, rect):
            assert rect == atlas.GUARDIAN_DUST_DIGITS
            return game.read_dust()

        monkeypatch.setattr(token_counter, "read", read)
        monkeypatch.setattr(enlighten, "button_cost", lambda game: game.read_cost())
        return g

    return make


EVENT = {"EventDecoratedHeroes": "1"}


def auto(**limits):
    return {"GuardianEnlighten": "1", **{k: str(v) for k, v in limits.items()}}


# the event's three a day (ported from the Decorated Heroes tests)


def test_event_three_at_x1_as_separate_clicks_on_the_trained_guardian_then_x20_back(screen):
    g = screen(EVENT)
    assert enlighten.enlighten(g) == 3
    assert g.clicks == [1, 1, 1] and g.dust == 8015 - 60
    assert g.displayed == 3
    assert g.mult == 20  # the user's multiplier is put back
    assert g.settings.get("EnlightenCountDaily") == "3"
    assert g.settings.get("EnlightenDustDaily") == "60"
    assert daily.event_enlighten_need(g.settings) == 0
    assert all(line.startswith("Guardian enlightenment (Decorated Heroes):") for line in g.lines)
    assert "(3/3 today, 60 dust today, 7,955 left)" in g.lines[-1]
    g.taps.clear()
    assert enlighten.enlighten(g) == 0  # nothing more today
    assert g.taps == []


def test_a_click_that_spends_no_dust_is_not_counted(screen):
    """One of the event's own x1 clicks: not counted, another cycle tries again."""
    g = screen(EVENT, taken=False)
    assert enlighten.enlighten(g) == 0
    assert daily.event_enlighten_need(g.settings) == 3
    assert g.settings.get("EnlightenDustDaily") == "0"
    assert g.captures == ["enlighten-not-taken.png"]
    assert g.lines[-1].endswith("the enlightenment spent no strange dust, not counted")
    assert g.mult == 20


def test_clicks_the_counter_never_shows_stop_after_two_a_day(screen):
    g = screen(EVENT, taken=False)
    for _ in range(4):  # four cycles
        enlighten.enlighten(g)
    assert g.captures.count("enlighten-not-taken.png") == enlighten.MAX_UNCONFIRMED
    assert not enlighten.due(g)


def test_not_enough_dust_stops(screen):
    g = screen(EVENT, dust=30, mult=1)
    assert enlighten.enlighten(g) == 1
    assert any("not green" in line for line in g.lines)


def test_unreadable_multiplier_never_enlightens(screen):
    g = screen(EVENT, mult_readable=False)
    assert enlighten.enlighten(g) == 0
    assert g.clicks == [] and "enlighten-multiplier.png" in g.captures


def test_a_label_that_breaks_the_cycle_is_not_trusted(screen, monkeypatch):
    """x20 -> (click) -> reads x5: not the next step of the cycle, nothing is spent."""
    g = screen(EVENT)
    reads = iter([20, 20, 5, 5, 5, 5, 5, 5, 5, 5])
    monkeypatch.setattr(
        enlighten.multiplier, "read_multiplier", lambda game, rect, anchor: next(reads)
    )
    assert enlighten.enlighten(g) == 0
    assert g.clicks == []


def test_a_label_read_x1_on_x10_is_caught_by_the_cost_before_any_click(screen):
    """The label reads x1 while the screen holds x10: the button asks 200, not 20."""
    g = screen(EVENT, mult=10, label=1)
    assert enlighten.enlighten(g) == 0
    assert g.clicks == [] and g.dust == 8015
    assert "enlighten-cost.png" in g.captures


@pytest.mark.parametrize(
    "settings, counter",
    [
        (EVENT, {"blind_reads": 1}),  # the visit's first counter read fails, then it reads
        (auto(MaxEnlighten=20), {"blind_reads": 3}),  # still blind at the plan: 20 x1 clicks
        (EVENT, {"dust_readable": False}),  # never read
        (auto(MaxEnlighten=4), {"dust_readable": False}),
    ],
)
def test_a_label_read_x1_on_x10_is_caught_by_the_cost_with_the_counter_unread(
    screen, settings, counter
):
    """Review 2026-09-28: a visit that had not read the counter took the 200 the button asks
    for the price of one enlightenment, and every click at the real x10 bought 10 (the event
    alone: 30 enlightenments, 600 dust, counted 3). The price stays 20: nothing is spent."""
    g = screen(settings, mult=10, label=1, **counter)
    assert enlighten.enlighten(g) == 0
    assert g.clicks == [] and g.dust == 8015
    assert "enlighten-cost.png" in g.captures
    assert g.settings.get("EnlightenCountDaily") == "0"
    assert g.settings.get("EnlightenDustDaily") == "0"


@pytest.mark.parametrize(
    "settings",
    # the automation: a reserve that leaves 3 x1 clicks and still allows more afterwards
    [EVENT, auto(MaxEnlighten=0, EnlightenDustReserve=7940)],
)
def test_a_click_that_takes_more_than_it_should_stops_for_the_day(screen, settings):
    """The label reads x1 while the screen holds x10 and the cost is unreadable: one click
    takes 200, counted as 10 with the true dust, then nothing more this game day."""
    g = screen(settings, mult=10, label=1, cost_readable=False)
    assert enlighten.enlighten(g) == 10
    assert g.clicks == [10] and g.dust == 8015 - 200
    assert g.settings.get("EnlightenCountDaily") == "10"
    assert g.settings.get("EnlightenDustDaily") == "200"
    assert "enlighten-multiplier.png" in g.captures
    assert not enlighten.due(g)
    assert enlighten.enlighten(g) == 0 and g.clicks == [10]


# the automation


def test_a_reserve_keeps_its_dust_and_the_rest_goes_at_x20_and_x5(screen):
    g = screen(auto(MaxEnlighten=0, EnlightenDustReserve=2000), dust=2500)
    assert enlighten.enlighten(g) == 25
    assert g.clicks == [20, 5] and g.dust == 2000
    assert g.settings.get("EnlightenCountDaily") == "25"
    assert g.settings.get("EnlightenDustDaily") == "500"
    assert g.mult == 20
    assert g.mult_taps == 4  # x20 -> x1 -> x5, then x10 -> x20
    assert "Guardian enlightenment: guardian 3 x20 (20 today, 400 dust today, 2,100 left)" in (
        g.lines
    )
    assert not enlighten.due(g)  # down to the reserve: the next trip waits an hour


def test_a_visit_down_to_the_reserve_rests_the_screen_an_hour(screen, clock):
    g = screen(auto(MaxEnlighten=0, EnlightenDustReserve=2000), dust=2500)
    enlighten.enlighten(g)
    assert not enlighten.due(g)
    g.dust += 20  # the dust comes back
    clock.now += enlighten.PAUSE_S + 1
    assert enlighten.due(g) and enlighten.enlighten(g) == 1


def test_the_daily_dust_cap(screen):
    g = screen(auto(MaxEnlighten=0, MaxEnlightenDust=1000))
    assert enlighten.enlighten(g) == 50
    assert g.clicks == [20, 20, 10] and g.dust == 8015 - 1000
    assert g.mult == 20
    assert not enlighten.due(g)  # the cap is reached: no more trips today
    daily.mark_daily_reset(g.settings)
    assert enlighten.due(g)


@pytest.mark.parametrize(
    "limits, dust_cap, count_cap",
    [({"MaxEnlighten": 0, "MaxEnlightenDust": 1000}, 1000, None), ({"MaxEnlighten": 20}, None, 20)],
)
def test_an_automation_click_the_counter_never_shows_counts_as_spent(
    screen, clock, monkeypatch, limits, dust_cap, count_cap
):
    """Review 2026-09-28: the first x20 click took its 400 dust but the counter never showed
    it; left uncounted, the next cycle planned the whole cap again (1,400 dust for a cap of
    1,000). Counted as spent, no cycle ever goes past the cap or the count."""
    g = screen(auto(**limits))
    real = token_counter.wait_drop
    drops = []

    def wait_drop(game, rect, before, timeout_ms):
        drops.append(before)
        return None if len(drops) == 1 else real(game, rect, before, timeout_ms)

    monkeypatch.setattr(token_counter, "wait_drop", wait_drop)
    for _ in range(5):  # cycles, an hour apart
        enlighten.enlighten(g)
        clock.now += enlighten.PAUSE_S + 1
    assert not enlighten.due(g)
    assert g.clicks[0] == 20 and "enlighten-not-taken.png" in g.captures
    assert any("never showed the x20 click, counted as spent (400 dust)" in x for x in g.lines)
    if dust_cap is not None:
        assert 8015 - g.dust <= dust_cap
        assert g.settings.get("EnlightenDustDaily") == str(dust_cap)
    if count_cap is not None:
        assert g.enlightened <= count_cap
        assert g.settings.get("EnlightenCountDaily") == str(count_cap)


def test_a_count_of_seven_is_one_x5_and_two_x1_from_where_the_label_stands(screen):
    g = screen(auto(MaxEnlighten=7), mult=1)
    assert enlighten.enlighten(g) == 7
    assert g.clicks == [1, 1, 5]  # x1 first: the label only steps forward
    assert g.mult == 1


@pytest.mark.parametrize(
    "count, cap, reserve, made",
    [
        (30, 500, 7800, 10),  # the reserve leaves 215 dust: 10
        (30, 300, 0, 15),  # the cap: 15
        (12, 1000, 5000, 12),  # the count
    ],
)
def test_combined_limits_the_strictest_wins(screen, count, cap, reserve, made):
    g = screen(auto(MaxEnlighten=count, MaxEnlightenDust=cap, EnlightenDustReserve=reserve))
    assert enlighten.enlighten(g) == made
    assert g.dust == 8015 - 20 * made


def test_event_first_at_x1_then_the_automation_at_higher_multipliers(screen):
    g = screen({**EVENT, **auto(MaxEnlighten=30)})
    assert enlighten.enlighten(g) == 30
    assert g.clicks == [1, 1, 1, 1, 1, 5, 20]  # 3 for the event, then 27 = x20 + x5 + 2 x1
    assert g.mult == 20
    assert all(line.startswith("Guardian enlightenment:") for line in g.lines)


def test_the_event_spends_even_below_the_reserve(screen):
    g = screen({**EVENT, **auto(EnlightenDustReserve=9000)})
    assert enlighten.enlighten(g) == 3
    assert g.clicks == [1, 1, 1]
    assert any("9,000 kept in reserve" in line for line in g.lines)


def test_spend_everything_stops_at_the_clicks_per_visit_cap(screen):
    g = screen(auto(MaxEnlighten=0), dust=20000)
    assert enlighten.enlighten(g) == 20 * enlighten.MAX_CLICKS_PER_VISIT
    assert g.clicks == [20] * enlighten.MAX_CLICKS_PER_VISIT
    assert g.dust == 20000 - 400 * enlighten.MAX_CLICKS_PER_VISIT
    assert "clicks this visit" in g.lines[-1]
    assert enlighten.due(g)  # the rest goes next cycle


def test_a_wrong_cost_at_x5_is_made_with_x1_clicks(screen):
    g = screen(auto(MaxEnlighten=7), mult=1, wrong_cost={5: 125})
    assert enlighten.enlighten(g) == 7
    assert g.clicks == [1] * 7
    assert "enlighten-cost.png" in g.captures
    assert g.mult == 1


def test_an_unreadable_cost_keeps_to_x1(screen):
    g = screen(auto(MaxEnlighten=0, EnlightenDustReserve=2000), dust=2500, cost_readable=False)
    assert enlighten.enlighten(g) == 25
    assert g.clicks == [1] * 25 and g.dust == 2000
    assert g.mult == 20


def test_a_wrong_cost_at_x1_spends_nothing(screen):
    g = screen(auto(MaxEnlighten=3), mult=1, wrong_cost={1: 25})
    assert enlighten.enlighten(g) == 0
    assert g.clicks == [] and "enlighten-cost.png" in g.captures


@pytest.mark.parametrize(
    "limits", [{"EnlightenDustReserve": 2000}, {"MaxEnlightenDust": 1000}, {"MaxEnlighten": 0}]
)
def test_an_unreadable_counter_spends_nothing_under_a_dust_limit_or_no_limit(screen, limits):
    g = screen(auto(**{"MaxEnlighten": 0, **limits}), dust_readable=False)
    assert enlighten.enlighten(g) == 0
    assert g.clicks == [] and g.mult == 20
    assert any("not readable" in line for line in g.lines)


def test_an_unreadable_counter_with_a_count_only_makes_x1_clicks(screen):
    g = screen(auto(MaxEnlighten=4), dust_readable=False)
    assert enlighten.enlighten(g) == 4
    assert g.clicks == [1, 1, 1, 1] and g.mult == 20
    assert g.settings.get("EnlightenDustDaily") == "80"


def test_an_unreadable_counter_still_makes_the_events_three(screen):
    g = screen({**EVENT, **auto(EnlightenDustReserve=2000)}, dust_readable=False)
    assert enlighten.enlighten(g) == 3
    assert g.clicks == [1, 1, 1]


def test_a_blocking_reserve_is_said_once_a_day_and_the_screen_rests_an_hour(screen, clock):
    g = screen(auto(EnlightenDustReserve=9000))
    assert enlighten.enlighten(g) == 0 and g.clicks == []
    assert not enlighten.due(g)
    clock.now += enlighten.PAUSE_S + 1
    assert enlighten.due(g)
    assert enlighten.enlighten(g) == 0
    assert sum("kept in reserve" in line for line in g.lines) == 1


def test_a_stop_is_not_followed_by_a_multiplier_click(screen, monkeypatch):
    g = screen(auto(MaxEnlighten=3))

    def stop(*a):
        raise BotStopped

    monkeypatch.setattr(token_counter, "wait_drop", stop)
    with pytest.raises(BotStopped):
        enlighten.enlighten(g)
    assert g.mult == 1 and g.taps[-1] == atlas.GUARDIAN_ENLIGHTEN


# -- guardian(): the trip to the screen ------------------------------------------------------


@pytest.fixture
def visit(monkeypatch, screen):
    calls = []
    monkeypatch.setattr(guardian, "big_close", lambda g: calls.append("close"))
    monkeypatch.setattr(guardian, "upgrade_on_guardian_screen", lambda g: calls.append("chaos"))

    def make(settings, **kw):
        g = screen(settings, **kw)
        return g, calls

    return make


def test_enlightenment_alone_opens_the_screen_for_itself(visit):
    g, calls = visit({"GuardianVisit": "0", **auto(MaxEnlighten=3)})
    guardian.guardian(g)
    assert g.opened and g.clicks == [1, 1, 1]
    assert g.probes and set(g.probes) == {atlas.GUARDIAN_ENLIGHTEN_READY}  # no evolve/training
    assert calls == ["close"]


def test_everything_off_nothing_is_touched(visit):
    g, calls = visit({"GuardianVisit": "0"})
    guardian.guardian(g)
    assert not g.focused and not g.opened and g.taps == [] and calls == []


def test_a_visit_without_enlightenment_does_not_touch_the_button(visit):
    g, calls = visit({"GuardianVisit": "1"})
    guardian.guardian(g)
    assert g.opened and g.clicks == [] and g.displayed is None
    assert calls == ["chaos", "close"]


def test_a_visit_that_could_not_spend_saves_the_next_trips(visit, clock):
    g, _ = visit({"GuardianVisit": "0", **auto(EnlightenDustReserve=9000)})
    guardian.guardian(g)
    assert g.opened
    g.opened = False
    guardian.guardian(g)
    assert not g.opened  # an hour's rest
    clock.now += enlighten.PAUSE_S + 1
    guardian.guardian(g)
    assert g.opened


def test_the_event_is_tried_every_cycle_despite_the_rest(visit):
    g, _ = visit({"GuardianVisit": "0", **EVENT, **auto()}, dust=10)
    guardian.guardian(g)
    assert g.opened and g.clicks == [] and any("not green" in line for line in g.lines)
    g.opened = False
    guardian.guardian(g)
    assert g.opened  # the event still needs its 3
