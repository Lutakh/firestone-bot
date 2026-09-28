"""Decorated Heroes switch turned off by the bot: active cards told apart on real strips of
the events list (2026-09-28), two looks on two openings before any verdict, no verdict on
anything unexpected, a look every 30 min or at every cycle near the daily reset."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from firestone_bot import daily
from firestone_bot.features import claim_events, event_watch
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas
from tests.test_decorated_heroes import FakeEvents, patch_events

FIX = Path(__file__).parent / "fixtures"
GONE_LINE = (
    "Decorated Heroes: the event is no longer in the events list (checked twice), switch turned off"
)
GONE_BEAT = ("Decorated Heroes event ended: switch turned off", True)


def _stamp(hours_ago):
    """A LastTokenReset `hours_ago` (local time, AHK A_Now format, as state.hours_since)."""
    past = datetime.now() - timedelta(hours=hours_ago)  # noqa: DTZ005
    return past.strftime("%Y%m%d%H%M%S")


@pytest.fixture
def now(monkeypatch):
    clock = [50_000_000]
    monkeypatch.setattr(event_watch, "_now_ms", lambda: clock[0])
    return clock


@pytest.fixture
def watch(monkeypatch, tmp_path, now):
    """make(settings, **FakeEvents options): the switch on and saved, no bell anywhere, the
    last daily reset 1 h ago (the next one is not near)."""
    patch_events(monkeypatch, [])

    def make(settings=None, **kw):
        s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        values = {"EventDecoratedHeroes": "1", "Events": "1", "LastTokenReset": _stamp(1)}
        for k, v in {**values, **(settings or {})}.items():
            s.set(k, v)
        s.save()
        kw.setdefault("bells", ())
        return FakeEvents(s, **kw)

    return make


def _saved(tmp_path):
    return Settings.load(str(tmp_path / "settings.ini"))


def _between_openings(g):
    icon = [i for i, p in enumerate(g.taps) if p == g.ms.events_icon]
    return g.taps[icon[0] : icon[1]]


def _stays_on(g):
    return g.settings.flag("EventDecoratedHeroes") and g.beats == []


# -- active cards --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, active",
    [("active-dh", True), ("upcoming-card", False), ("upcoming-header", False), ("empty", False)],
)
def test_active_cards_told_apart_on_the_owner_list(name, active):
    """Bands across a slot, 2026-09-28: the Decorated Heroes card (full colour), a grey
    upcoming card through its yellow title, the lavender "Upcoming events" header and the
    empty list background."""
    share = event_watch.colourful_share(np.load(FIX / f"events-strip-{name}.npy"))
    assert (share >= event_watch.ACTIVE_SHARE_MIN) == active
    assert share > 0.4 if active else share < 0.1


def test_strips_cross_the_card_slots():
    for (x1, y1, x2, y2), card in zip(atlas.EVENTS_CARD_STRIPS, atlas.EVENTS_CARDS, strict=True):
        assert (x2 - x1, y2 - y1) == (880, 30)  # the fixtures' size
        assert (x1 + x2) // 2 == card.x and (y1 + y2) // 2 == card.y


# -- verdicts ------------------------------------------------------------------------------


def test_event_found_without_a_bell_keeps_the_switch_on(watch, now):
    g = watch(cards=("dh",))
    claim_events.claim_events(g)
    assert g.openings == 1 and g.card_taps() == [0]
    assert atlas.DH_PAGE_CLOSE in g.taps
    assert _stays_on(g) and g.captures == []
    assert g.vars[event_watch._seen_key(g)] == now[0]
    assert not event_watch.check_due(g)


def test_event_gone_on_two_openings_turns_the_switch_off(watch, tmp_path):
    g = watch(
        settings={"Token": "1", "MaxTokens": "10", "Crystal": "1", "MaxCrystals": "5"},
        cards=("basic",),
    )
    assert (daily.token_limit(g.settings), daily.crystal_limit(g.settings)) == (12, 15)
    claim_events.claim_events(g)
    assert g.openings == 2 and g.card_taps() == [0, 0]
    between = _between_openings(g)
    assert atlas.EVENTS_LIST_CLOSE in between and atlas.EVENTS_PAGE_CLOSE in between
    assert g.slept >= event_watch.CONFIRM_PAUSE_MS
    assert not g.settings.flag("EventDecoratedHeroes")
    saved = _saved(tmp_path)
    assert not saved.flag("EventDecoratedHeroes") and saved.get("MaxTokens") == "10"
    assert GONE_LINE in g.lines and g.beats == [GONE_BEAT]
    assert g.captures == ["decorated-heroes-gone.png"]
    # the rest of the cycle spends with the user's own limits
    assert (daily.token_limit(g.settings), daily.crystal_limit(g.settings)) == (10, 5)
    assert not event_watch.check_due(g)
    assert g.taps[-1] == atlas.EVENTS_LIST_CLOSE  # claim_events closes the list as before


@pytest.mark.parametrize("cards", [(), ("upcoming", "upcoming")])
def test_no_active_card_twice_turns_the_switch_off(watch, cards):
    """An empty list, or only upcoming cards (grey: never opened, even a coming Decorated
    Heroes)."""
    g = watch(cards=cards)
    claim_events.claim_events(g)
    assert g.openings == 2 and g.card_taps() == []
    assert not g.settings.flag("EventDecoratedHeroes") and g.beats == [GONE_BEAT]


def test_list_never_shown_gives_no_verdict(watch):
    g = watch(list_ok=False)
    claim_events.claim_events(g)
    assert g.card_taps() == [] and g.openings == 1
    assert _stays_on(g)
    assert "Decorated Heroes: no verdict from the events list, the switch stays on" in g.lines


def test_the_second_look_finds_the_event(watch):
    """The first look misses it (a card that showed late): the second one sees it."""
    g = watch(cards=("basic",), later_cards=("dh", "basic"))
    claim_events.claim_events(g)
    assert g.openings == 2 and g.card_taps() == [0, 0]
    assert _stays_on(g)
    assert "Decorated Heroes: the event is still in the events list (card 1)" in g.lines


def test_a_slow_event_page_is_waited_for(watch):
    g = watch(cards=("basic", "dh"), dh_slow=event_watch.PAGE_POLLS - 1)
    claim_events.claim_events(g)
    assert g.openings == 1 and g.card_taps() == [0, 1]
    assert _stays_on(g)


def test_an_event_page_slower_than_the_patience_gives_no_verdict(watch):
    """Not recognised in time, the page is not taken for another event: its X does not
    close it, the list does not come back."""
    g = watch(cards=("dh",), dh_slow=100)
    claim_events.claim_events(g)
    assert g.openings == 1
    assert _stays_on(g)
    assert g.captures == ["events-unknown-card-1.png"]


def test_an_unknown_page_gives_no_verdict(watch):
    g = watch(cards=("unknown", "basic"))
    claim_events.claim_events(g)
    assert g.card_taps() == [0]  # nothing more is opened blind
    assert _stays_on(g)
    assert g.captures == ["events-unknown-card-1.png"]


def test_a_card_that_opens_nothing_gives_no_verdict(watch):
    g = watch(cards=("none",))
    claim_events.claim_events(g)
    assert g.openings == 1 and _stays_on(g)
    assert "Decorated Heroes check: card 1 opened nothing" in g.lines


def test_four_active_cards_give_no_verdict(watch):
    """Only four slots are modelled: a fifth active card could be below."""
    g = watch(cards=("basic",) * 4)
    claim_events.claim_events(g)
    assert g.openings == 1 and g.card_taps() == [0, 1, 2, 3]
    assert _stays_on(g)


def test_event_seen_through_its_bell_needs_no_other_look(watch):
    g = watch(bells=(0, 1))
    claim_events.claim_events(g)
    assert g.openings == 1 and g.card_taps() == [0, 1]  # the bell cards only
    assert _stays_on(g)


def test_a_basic_card_bell_is_not_a_look_at_the_event(watch):
    g = watch(bells=(1,))
    claim_events.claim_events(g)
    assert g.card_taps() == [1, 0]  # the bell, then the check
    assert _stays_on(g) and g.vars[event_watch._seen_key(g)]


# -- when --------------------------------------------------------------------------------


def test_a_look_every_30_min(watch, now):
    g = watch(cards=("dh",))
    event_watch.note_seen(g)
    now[0] += 5 * 60_000
    claim_events.claim_events(g)
    assert g.openings == 0
    assert g.lines == ["Events: no bell on the button, nothing to claim"]
    now[0] += 25 * 60_000
    claim_events.claim_events(g)
    assert g.openings == 1 and _stays_on(g)


@pytest.mark.parametrize("stamp", [_stamp(23.5), _stamp(40), ""])
def test_a_look_at_every_cycle_near_the_reset(watch, now, stamp):
    """23 h after the last reset (or none known): the first cycle after the reset looks
    before the shop detects it, so that day's spending never uses the event's limits."""
    g = watch(settings={"LastTokenReset": stamp}, cards=("dh",))
    for _ in range(2):
        claim_events.claim_events(g)
        now[0] += 60_000
    assert g.openings == 2 and _stays_on(g)


def test_a_new_game_day_looks_again(watch):
    g = watch(cards=("dh",))
    event_watch.note_seen(g)
    assert not event_watch.check_due(g)
    g.settings.set("LastTokenReset", _stamp(0.01))  # the shop detected the reset
    assert event_watch.check_due(g)


def test_switch_off_keeps_the_early_return(watch):
    g = watch(settings={"EventDecoratedHeroes": "0"}, cards=())
    claim_events.claim_events(g)
    assert g.openings == 0 and g.taps == []
    assert g.lines == ["Events: no bell on the button, nothing to claim"]
    assert not event_watch.check_due(g)
