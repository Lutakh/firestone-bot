"""Decorated Heroes event: limits raised by the switch, stars claimed on the event page,
three guardian enlightenments a day at x1 with the user's multiplier put back."""

from pathlib import Path

import numpy as np
import pytest

from firestone_bot import daily
from firestone_bot.features import claim_events, decorated_heroes
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
    assert daily.event_enlighten_need(s) == 0 and not daily.enlighten_wanted(s)  # switch off
    s.set("EventDecoratedHeroes", "1")
    assert daily.event_enlighten_need(s) == 3 and daily.enlighten_wanted(s)
    for _ in range(3):
        daily.note_enlighten(s)
    assert daily.event_enlighten_need(s) == 0 and not daily.enlighten_wanted(s)
    assert s.get("EnlightenDustDaily") == "60"
    daily.mark_daily_reset(s)
    assert daily.event_enlighten_need(s) == 3


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


STRIPS = {  # bands across a card slot, captured on the owner's list 2026-09-28
    name: np.load(FIX / f"events-strip-{name}.npy")
    for name in ("active-dh", "upcoming-card", "upcoming-header", "empty")
}
PAGES = ("dh", "basic", "unknown")  # card kinds whose tap opens a page over the list


class FakeEvents:
    """Events list with cards; by default card 0 is the Decorated Heroes event, card 1 a
    basic event. Card kinds: "dh"; "basic" (its page closes with EVENTS_PAGE_CLOSE, whose X
    ring it shows); "unknown" (a page nothing here closes); "none" (drawn in colour, opens
    nothing); "upcoming" (grey, opens nothing). Slots past the cards show the empty list.
    `later_cards`: the list from its second opening on; `list_ok=False`: it never shows;
    `dh_slow`: reads of the event page's X that miss before the page is there."""

    def __init__(
        self,
        settings,
        bells=(0, 1),
        dh_tab="challenges",
        cards=("dh", "basic"),
        later_cards=None,
        list_ok=True,
        dh_slow=0,
    ):
        self.settings = settings
        self.bells = set(bells)
        self.dh_tab = dh_tab  # the tab the event page opens on
        self.cards = tuple(cards)
        self.later_cards = later_cards
        self.list_ok = list_ok
        self.dh_slow = dh_slow
        self.list_open = False
        self.openings = 0
        self.page = None
        self.taps = []
        self.lines = []
        self.beats = []
        self.captures = []
        self.slept = 0
        self.vars = {}
        self.style = "new"

    @property
    def ms(self):
        from firestone_bot.vision import layouts

        return layouts.NEW

    def focus(self):
        pass

    def open_screen(self, point, expect, *a, **kw):
        self.taps.append(point)  # the events button
        self.openings += 1
        if self.openings > 1 and self.later_cards is not None:
            self.cards = tuple(self.later_cards)
        self.list_open = self.list_ok
        self.page = None
        return self.list_ok

    def _kind(self):
        return None if self.page is None else self.cards[self.page]

    def _list_shown(self):
        return self.list_open and self.page is None

    def found(self, probe):
        if probe == atlas.EVENTS_CLOSE_X:
            return self._list_shown()
        kind = self._kind()
        if probe == atlas.EVENTS_PAGE_CLOSE_X:
            return kind == "basic"
        if kind != "dh":
            return False
        if probe == atlas.DH_PAGE_CLOSE_X and self.dh_slow:
            self.dh_slow -= 1
            return False
        challenges = self.dh_tab == "challenges"
        return {
            atlas.DH_PAGE_CLOSE_X: True,
            atlas.DH_CHALLENGES_TAB: challenges,
            atlas.DH_MEDALS_TAB: self.dh_tab != "medals",
            atlas.DH_CHALLENGES_TAB_IDLE: not challenges,
            atlas.DH_MEDALS_TAB_SELECTED: self.dh_tab == "medals",
        }.get(probe, False)

    def region_image(self, rect, anchor=None):
        slot = atlas.EVENTS_CARD_STRIPS.index(rect)
        kind = self.cards[slot] if self._list_shown() and slot < len(self.cards) else None
        if kind is None:
            return STRIPS["empty"]
        return STRIPS["upcoming-card" if kind == "upcoming" else "active-dh"]

    def wait_still(self):
        pass

    def move_to(self, point):
        pass

    def sleep(self, ms):
        self.slept += ms

    def tap(self, point, settle_ms=1500, expect=None):
        self.taps.append(point)
        kind = self._kind()
        if point == atlas.DH_CHALLENGES_TAB_BUTTON:
            self.dh_tab = "challenges"
        elif point in atlas.EVENTS_CARDS:
            slot = atlas.EVENTS_CARDS.index(point)
            if self._list_shown() and slot < len(self.cards) and self.cards[slot] in PAGES:
                self.page = slot
        elif (point == atlas.DH_PAGE_CLOSE and kind == "dh") or (
            point == atlas.EVENTS_PAGE_CLOSE and kind == "basic"
        ):
            self.bells.discard(self.page)
            self.page = None
        elif point == atlas.EVENTS_LIST_CLOSE and self.page is None:
            self.list_open = False

    def status(self, text):
        self.lines.append(text)

    def heartbeat(self, msg, is_stop=False, important=False):
        self.beats.append((msg, important))

    def toast(self, *a):
        pass

    def save_diagnostic(self, name):
        self.captures.append(name)

    def card_taps(self):
        return [atlas.EVENTS_CARDS.index(p) for p in self.taps if p in atlas.EVENTS_CARDS]


def patch_events(monkeypatch, claimed):
    """Bells as the fake holds them, no main-menu check, the event page's claim recorded."""

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


@pytest.fixture
def events(monkeypatch, tmp_path):
    claimed = []
    patch_events(monkeypatch, claimed)

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


def test_a_card_bell_without_a_challenges_bell_is_captured_once_a_game_day(events):
    """A card whose bell stays lit with nothing on its Challenges tab was logged as "has no
    Challenges tab" and captured at every cycle (~1000 a day, 2026-09-18..25); the owner's
    basic event pages do have that tab (captures 2026-09-26/27), only its bell is missing."""
    g, _ = events(Events="1", EventDecoratedHeroes="0", LastTokenReset="20260928100016")
    for _ in range(3):
        g.bells = {1}
        claim_events.claim_events(g)
    assert g.captures == ["events-other-card-2.png"]
    assert "Events: card 2, no bell on its Challenges tab, nothing to claim" in g.lines
    g.settings.set("LastTokenReset", "20260929100021")  # the next game day
    g.bells = {1}
    claim_events.claim_events(g)
    assert g.captures == ["events-other-card-2.png"] * 2


# -- enlightenments --------------------------------------------------------------------------
# The event's three a day are made by features/enlighten.py: see tests/test_enlighten.py.
