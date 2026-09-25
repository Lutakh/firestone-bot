"""Decorated Heroes event: limits raised by the switch, stars claimed on the event page,
three guardian enlightenments a day at x1 with the user's multiplier put back."""

from pathlib import Path

import numpy as np
import pytest

from firestone_bot import daily
from firestone_bot.features import claim_events, decorated_heroes, token_counter
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas

FIX = Path(__file__).parent / "fixtures"


def _settings(tmp_path, **values):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    for k, v in values.items():
        s.set(k, v)
    return s


# -- daily limits ----------------------------------------------------------------------------


def test_event_raises_lower_limits_and_keeps_higher_ones(tmp_path):
    s = _settings(tmp_path, Token="1", MaxTokens="10", Crystal="1", MaxCrystals="5")
    assert daily.token_limit(s) == 10 and daily.crystal_limit(s) == 5  # switch off
    s.set("EventDecoratedHeroes", "1")
    assert daily.token_limit(s) == 12 and daily.crystal_limit(s) == 15
    s.set("MaxTokens", "20")
    s.set("MaxCrystals", "0")  # no limit stays no limit
    assert daily.token_limit(s) == 20 and daily.crystal_limit(s) == 0
    s.set("TokenCountDaily", "12")
    assert daily.tokens_left(s) == 8


def test_event_alone_asks_for_exactly_the_challenge(tmp_path):
    """Token or Crystal off in the user's settings: the event plays 12 / hits 15, never the
    'no limit' a stored 0 would mean."""
    s = _settings(
        tmp_path, EventDecoratedHeroes="1", Token="0", MaxTokens="0", Crystal="0", MaxCrystals="0"
    )
    assert daily.token_limit(s) == 12 and daily.crystal_limit(s) == 15


def test_enlightenments_three_a_day_and_reset(tmp_path):
    s = _settings(tmp_path)
    assert daily.enlighten_left(s) == 0  # switch off
    s.set("EventDecoratedHeroes", "1")
    assert daily.enlighten_left(s) == 3
    for _ in range(3):
        daily.note_enlighten(s)
    assert daily.enlighten_left(s) == 0
    daily.mark_daily_reset(s)
    assert daily.enlighten_left(s) == 3


# -- event page ------------------------------------------------------------------------------


def _green_button():
    img = np.zeros((29, 141, 3), dtype=np.uint8)
    img[:, :] = (0x08, 0xA0, 0x0A)  # GREEN_BUTTON 0x0AA008, BGR
    img[10:18, 40:100] = 255  # the white "Claim"
    return img


@pytest.mark.parametrize("name", ["dh-claim-grey", "dh-claim-done-card", "dh-claim-completed-bar"])
def test_real_slots_without_a_reward_are_not_green(name):
    """Captured on the event page, 2026-09-25: a grey Claim, a card whose tiers are all
    claimed (no button) and a 'Completed' card."""
    assert decorated_heroes.green_share(np.load(FIX / f"{name}.npy")) < 0.01


def test_a_green_claim_button_is_claimable():
    assert decorated_heroes.green_share(_green_button()) > 0.5


class FakePage:
    """The event page: `green` holds the claimable card indices; a claim of a card whose
    next tier is also reached (in `next_tier`) leaves it green once more."""

    def __init__(self, green, next_tier=()):
        self.green = list(green)
        self.next_tier = list(next_tier)
        self.taps = []
        self.lines = []
        self.pointer = None

    def found(self, probe):
        return probe in (atlas.DH_CHALLENGES_TAB, atlas.DH_MEDALS_TAB)

    def region_image(self, rect, anchor=None):
        for i, (p, _) in enumerate(atlas.DH_CLAIMS):
            if rect == (p.x1, p.y1, p.x2, p.y2):
                grey = np.full((29, 141, 3), 0xB0, dtype=np.uint8)
                hovered = self.pointer == atlas.DH_CLAIMS[i][1]
                return _green_button() if i in self.green and not hovered else grey
        raise AssertionError(rect)

    def tap(self, point, settle_ms=1500, expect=None):
        self.pointer = point
        self.taps.append(point)
        for i, (_, button) in enumerate(atlas.DH_CLAIMS):
            if point == button:
                assert i in self.green, "a grey Claim was clicked"
                self.green.remove(i)
                if i in self.next_tier:
                    self.next_tier.remove(i)
                    self.green.append(i)

    def move_to(self, point):
        self.pointer = point

    def sleep(self, ms):
        pass

    def wait_still(self):
        pass

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        pass


def test_every_reached_tier_is_claimed():
    g = FakePage(green=[2, 3, 6], next_tier=[3])
    assert decorated_heroes.claim_page(g) == 4
    assert g.green == []


def test_nothing_green_nothing_clicked():
    g = FakePage(green=[])
    assert decorated_heroes.claim_page(g) == 0
    assert g.taps == []


# -- events list -----------------------------------------------------------------------------


class FakeEvents:
    """Events list with cards; card 0 is the Decorated Heroes event, card 1 a basic event."""

    def __init__(self, settings, bells=(0, 1), dh_tab="challenges"):
        self.settings = settings
        self.bells = set(bells)
        self.dh_tab = dh_tab  # the tab the event page opens on
        self.page = None
        self.taps = []
        self.lines = []
        self.style = "new"

    @property
    def ms(self):
        from firestone_bot.vision import layouts

        return layouts.NEW

    def focus(self):
        pass

    def open_screen(self, point, expect, *a, **kw):
        return True

    def found(self, probe):
        if self.page != 0:
            return False
        challenges = self.dh_tab == "challenges"
        return {
            atlas.DH_PAGE_CLOSE_X: True,
            atlas.DH_CHALLENGES_TAB: challenges,
            atlas.DH_MEDALS_TAB: self.dh_tab != "medals",
            atlas.DH_CHALLENGES_TAB_IDLE: not challenges,
            atlas.DH_MEDALS_TAB_SELECTED: self.dh_tab == "medals",
        }.get(probe, False)

    def wait_still(self):
        pass

    def move_to(self, point):
        pass

    def sleep(self, ms):
        pass

    def tap(self, point, settle_ms=1500, expect=None):
        self.taps.append(point)
        if point == atlas.DH_CHALLENGES_TAB_BUTTON:
            self.dh_tab = "challenges"
        elif point in atlas.EVENTS_CARDS:
            self.page = atlas.EVENTS_CARDS.index(point)
        elif point in (atlas.DH_PAGE_CLOSE, atlas.EVENTS_PAGE_CLOSE):
            self.bells.discard(self.page)
            self.page = None

    def status(self, text):
        self.lines.append(text)

    def toast(self, *a):
        pass

    def save_diagnostic(self, name):
        pass


@pytest.fixture
def events(monkeypatch, tmp_path):
    claimed = []

    def bell_in(g, probe):
        if probe is g.ms.events_bell:
            return bool(g.bells)
        if probe in atlas.EVENTS_CARD_BELLS:
            return atlas.EVENTS_CARD_BELLS.index(probe) in g.bells
        return False  # no Challenges tab bell on the basic card in this fake

    monkeypatch.setattr(claim_events.bells, "bell_in", bell_in)
    monkeypatch.setattr(claim_events, "main_menu", lambda g: None)
    monkeypatch.setattr(
        claim_events.decorated_heroes, "claim_page", lambda g: claimed.append(g.page) or 2
    )

    def make(**values):
        return FakeEvents(_settings(tmp_path, **values)), claimed

    return make


def test_event_page_claimed_and_the_next_card_still_visited(events):
    g, claimed = events(Events="1", EventDecoratedHeroes="1")
    claim_events.claim_events(g)
    assert claimed == [0]
    assert atlas.DH_PAGE_CLOSE in g.taps  # its own X, not the basic page's
    assert atlas.EVENTS_CARDS[1] in g.taps  # the card after it is not starved


def test_switch_off_the_event_page_is_closed_without_claiming(events):
    g, claimed = events(Events="1", EventDecoratedHeroes="0")
    claim_events.claim_events(g)
    assert claimed == []
    assert atlas.DH_PAGE_CLOSE in g.taps


@pytest.mark.parametrize("tab", ["medals", "exchange"])
def test_event_page_opened_on_another_tab_is_still_claimed(events, tab):
    """The game reopens a screen on the tab last viewed."""
    g, claimed = events(Events="1", EventDecoratedHeroes="1")
    g.dh_tab = tab
    claim_events.claim_events(g)
    assert atlas.DH_CHALLENGES_TAB_BUTTON in g.taps
    assert claimed == [0]
    assert atlas.EVENTS_PAGE_CLOSE not in g.taps[: g.taps.index(atlas.DH_PAGE_CLOSE)]


def test_switch_alone_claims_only_the_event(events):
    g, claimed = events(Events="0", EventDecoratedHeroes="1")
    claim_events.claim_events(g)
    assert claimed == [0]
    assert atlas.EVENTS_CHALLENGES_TAB not in g.taps


# -- enlightenments --------------------------------------------------------------------------


class FakeGuardian:
    """Guardian screen, first tab: multiplier cycle x20 -> x1 -> x5 -> x10 -> x20, the
    Enlightenment button green while dust covers the cost, dust counter read as a number."""

    CYCLE = (20, 1, 5, 10)

    def __init__(self, settings, dust=8015, mult=20, taken=True, mult_readable=True, lies_x1=False):
        self.settings = settings
        self.vars = {}
        self.lies_x1 = lies_x1  # the label reads x1 whatever the screen holds
        self.dust = dust
        self.mult = mult
        self.taken = taken
        self.mult_readable = mult_readable
        self.pointer = None
        self.displayed = None
        self.enlightened = 0
        self.lines = []
        self.captures = []

    def found(self, probe):
        assert probe is atlas.GUARDIAN_ENLIGHTEN_READY
        hovered = self.pointer == atlas.GUARDIAN_ENLIGHTEN
        return self.dust >= 20 * self.mult and not hovered

    def tap(self, point, settle_ms=1500, expect=None):
        self.pointer = point
        if point == atlas.GUARDIAN_MULTIPLIER:
            i = self.CYCLE.index(self.mult)
            self.mult = self.CYCLE[(i + 1) % len(self.CYCLE)]
        elif point == atlas.GUARDIAN_ENLIGHTEN:
            assert self.mult == 1 or self.lies_x1, f"enlightened at x{self.mult}"
            if self.taken:
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


@pytest.fixture
def guardian(monkeypatch, tmp_path):
    def make(**kw):
        s = _settings(tmp_path, EventDecoratedHeroes="1", GuardianTrain="3")
        g = FakeGuardian(s, **kw)
        monkeypatch.setattr(
            decorated_heroes.multiplier,
            "read_multiplier",
            lambda game, rect, anchor: (
                (1 if game.lies_x1 else game.mult) if game.mult_readable else None
            ),
        )
        monkeypatch.setattr(token_counter, "read", lambda game, rect: game.dust)
        return g

    return make


def test_three_enlightenments_at_x1_on_the_trained_guardian_then_x20_back(guardian):
    g = guardian()
    assert decorated_heroes.enlighten(g) == 3
    assert g.enlightened == 3 and g.dust == 8015 - 60
    assert g.displayed == 3
    assert g.mult == 20  # the user's multiplier is put back
    assert daily.enlighten_left(g.settings) == 0
    assert decorated_heroes.enlighten(g) == 0  # nothing more today


def test_a_click_that_spends_no_dust_is_not_counted(guardian):
    g = guardian(taken=False)
    assert decorated_heroes.enlighten(g) == 0
    assert daily.enlighten_left(g.settings) == 3
    assert g.captures == ["enlighten-not-taken.png"]


def test_not_enough_dust_stops(guardian):
    g = guardian(dust=30, mult=1)
    assert decorated_heroes.enlighten(g) == 1
    assert any("not green" in line for line in g.lines)


def test_unreadable_multiplier_never_enlightens(guardian):
    g = guardian(mult_readable=False)
    assert decorated_heroes.enlighten(g) == 0
    assert g.enlightened == 0


def test_a_click_that_takes_more_than_one_enlightenment_stops_for_the_day(guardian):
    """The label read x1 while the screen held x10: one click, then no more today."""
    g = guardian(mult=10, lies_x1=True)
    assert decorated_heroes.enlighten(g) == 1
    assert g.dust == 8015 - 200
    assert daily.enlighten_left(g.settings) == 0
    assert "enlighten-multiplier.png" in g.captures


def test_a_label_that_breaks_the_cycle_is_not_trusted(guardian, monkeypatch):
    """x20 -> (click) -> reads x5: not the next step of the cycle, nothing is spent."""
    g = guardian()
    reads = iter([20, 20, 5, 5, 5, 5, 5, 5, 5, 5])
    monkeypatch.setattr(
        decorated_heroes.multiplier, "read_multiplier", lambda game, rect, anchor: next(reads)
    )
    assert decorated_heroes.enlighten(g) == 0
    assert g.enlightened == 0


def test_clicks_the_counter_never_shows_stop_after_two_a_day(guardian):
    g = guardian(taken=False)
    for _ in range(4):  # four cycles
        decorated_heroes.enlighten(g)
    assert g.captures.count("enlighten-not-taken.png") == decorated_heroes.MAX_UNCONFIRMED
