"""Decorated Heroes switch turned off by the bot: active cards told apart on real strips of
the events list (2026-09-28), read with the list wheeled back to its top, two looks on two
openings before any verdict, no verdict on anything unexpected (a page not recognised
either way included), a look every 30 min or at every cycle near the daily reset, a look
without a verdict retried once and then every 30 min. Turned on by the bot with the auto
switch (2026-09-29): one look once a game day and every 3 h while the switch is off, the
event's page seen through its bell turning it on and claimed in the same visit."""

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
    "Decorated Heroes: the event is not active in the events list (checked twice), switch "
    "turned off"
)
GONE_BEAT = ("Decorated Heroes event not active: switch turned off", True)


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
    # each look: the game in front, then the list wheeled to its top, then the strips read
    assert _looks(g) == [["focus", "wheel", "read"]] * 2


def _looks(g):
    """What each look did before its first strip read (the trace from each wheel back to the
    focus call before it)."""
    looks, current = [], []
    for step in g.trace:
        if step == "focus":
            current = ["focus"]
        elif step == "wheel":
            current.append("wheel")
        elif step == "read" and current:
            looks.append([*current, "read"])
            current = []
    return looks


def test_a_list_left_scrolled_is_wheeled_back_to_its_top(watch):
    """The game reopens the list where it was left (the user scrolled down to read the
    upcoming events): the view then shows the "Upcoming events" header and grey cards only,
    the event's card above it. Read like that, the list said "gone" twice (review
    2026-09-28)."""
    g = watch(cards=("dh", "header", "upcoming", "upcoming", "upcoming"), scrolled=1)
    claim_events.claim_events(g)
    assert g.trace.index("wheel") < g.trace.index("read")
    assert g.openings == 1 and g.card_taps() == [0]
    assert _stays_on(g) and g.vars[event_watch._seen_key(g)]
    assert "Decorated Heroes: the event is still in the events list (card 1)" in g.lines


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


def test_a_page_not_recognised_gives_no_verdict_even_when_it_closes(watch):
    """Only a page that shows another event's X ring counts as another event: a Decorated
    Heroes page that is_page misses (another client, a new tab colour) may close on that X
    too, and would have been taken for another event twice (review 2026-09-28)."""
    g = watch(cards=("unrecognised", "basic"))
    claim_events.claim_events(g)
    assert g.openings == 1 and g.card_taps() == [0]
    assert atlas.EVENTS_PAGE_CLOSE in g.taps  # left the way the other pages are
    assert _stays_on(g)
    assert g.captures == ["events-unknown-card-1.png"]
    assert (
        "Decorated Heroes check: card 1 opened a page that is not recognised (neither the "
        "event's nor another event's)"
    ) in g.lines
    assert "Decorated Heroes: no verdict from the events list, the switch stays on" in g.lines


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


@pytest.mark.parametrize(
    "cards, captures",
    [
        (("basic",) * 4, []),
        (("none",), ["events-card-1-no-page.png"]),
        (("unrecognised",), ["events-unknown-card-1.png"]),
    ],
)
def test_a_look_without_a_verdict_is_retried_once_then_every_30_min(watch, now, cards, captures):
    """No verdict recorded nothing: the list and every active page were opened, and captured,
    at every cycle all day (review 2026-09-28). A retry at the next cycle (the miss may pass),
    then the sightings' 30-min pace; the captures once a game day."""
    g = watch(cards=cards)
    for _ in range(5):
        claim_events.claim_events(g)
        now[0] += 90_000
    assert g.openings == event_watch.NO_VERDICT_LOOKS == 2
    assert g.lines[-1] == "Events: no bell on the button, nothing to claim"
    now[0] += event_watch.RECHECK_MS
    claim_events.claim_events(g)
    assert g.openings == 3
    claim_events.claim_events(g)
    assert g.openings == 3  # again 30 min apart
    assert _stays_on(g) and g.captures == captures
    g.settings.set("LastTokenReset", _stamp(0.01))  # the next game day: looks, captures again
    claim_events.claim_events(g)
    assert g.openings == 4 and g.captures == captures * 2


def test_near_the_reset_a_look_without_a_verdict_is_retried_at_every_cycle(watch, now):
    g = watch(settings={"LastTokenReset": _stamp(23.5)}, cards=("none",))
    for _ in range(4):
        claim_events.claim_events(g)
        now[0] += 60_000
    assert g.openings == 4 and _stays_on(g)
    assert g.captures == ["events-card-1-no-page.png"]


def test_a_verdict_starts_the_retries_over(watch, now):
    """A miss after a sighting is retried at the next cycle, not 30 min later."""
    g = watch(cards=("none",))
    for _ in range(2):
        claim_events.claim_events(g)
        now[0] += 60_000
    assert not event_watch.check_due(g)
    event_watch.note_seen(g)  # e.g. the event's page opened through its bell
    now[0] += event_watch.RECHECK_MS
    claim_events.claim_events(g)  # no verdict again
    assert g.openings == 3 and event_watch.check_due(g)


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


# -- start (EventDecoratedHeroesAuto, owner request 2026-09-29) ------------------------------

AUTO = {"EventDecoratedHeroes": "0", "EventDecoratedHeroesAuto": "1"}
START_LINE = (
    "Events: no bell on the button, opening the events list to see whether the Decorated "
    "Heroes event has started"
)
ON_BEAT = ("Decorated Heroes event active: switch turned on", True)
NOT_YET_LINE = "Decorated Heroes: not active in the events list yet, the switch stays off"


def test_event_active_without_a_bell_turns_the_switch_on(watch, tmp_path, now):
    g = watch(settings={**AUTO, "Token": "1", "MaxTokens": "10"}, cards=("basic", "dh"))
    assert event_watch.start_due(g) and not event_watch.check_due(g)
    assert daily.token_limit(g.settings) == 10
    claim_events.claim_events(g)
    assert g.lines[0] == START_LINE
    assert g.openings == 1 and g.card_taps() == [0, 1]  # one look: every active card opened
    assert g.settings.flag("EventDecoratedHeroes")
    assert _saved(tmp_path).flag("EventDecoratedHeroes")  # the GUI and the next start follow
    assert (
        "Decorated Heroes: the event is active in the events list (card 2), switch turned on"
    ) in g.lines
    assert g.beats == [ON_BEAT]
    assert g.captures == ["decorated-heroes-started.png"]
    assert g.taps[-2:] == [atlas.DH_PAGE_CLOSE, atlas.EVENTS_LIST_CLOSE]
    # the rest of the cycle spends with the event's limits; no look of either kind is due
    assert daily.token_limit(g.settings) == 12
    assert not event_watch.start_due(g) and not event_watch.check_due(g)
    assert g.vars[event_watch._seen_key(g)] == now[0]


def test_no_event_keeps_the_switch_off_and_looks_again_in_3_h(watch, now):
    g = watch(settings=AUTO, cards=("basic",))
    claim_events.claim_events(g)
    assert g.openings == 1 and g.card_taps() == [0]
    assert not g.settings.flag("EventDecoratedHeroes") and g.beats == [] and g.captures == []
    assert g.vars[event_watch._start_key(g)] == now[0]  # the look recorded
    assert g.lines.count(NOT_YET_LINE) == 1
    now[0] += event_watch.START_RECHECK_MS - 60_000
    claim_events.claim_events(g)
    assert g.openings == 1
    assert g.lines[-1] == "Events: no bell on the button, nothing to claim"
    now[0] += 60_000
    claim_events.claim_events(g)
    assert g.openings == 2 and not g.settings.flag("EventDecoratedHeroes")
    assert g.lines.count(NOT_YET_LINE) == 1  # its line once a game day
    g.settings.set("LastTokenReset", _stamp(0.01))  # the shop detected the reset
    assert event_watch.start_due(g)
    claim_events.claim_events(g)
    assert g.openings == 3 and g.lines.count(NOT_YET_LINE) == 2


def test_a_start_look_without_a_verdict_keeps_the_switch_off_for_3_h(watch, now):
    g = watch(settings=AUTO, list_ok=False)
    claim_events.claim_events(g)
    assert g.openings == 1 and not g.settings.flag("EventDecoratedHeroes")
    assert "Decorated Heroes start check: the events list is not on screen" in g.lines
    assert "Decorated Heroes: no verdict from the events list, the switch stays off" in g.lines
    assert NOT_YET_LINE not in g.lines
    assert not event_watch.start_due(g)
    now[0] += event_watch.START_RECHECK_MS
    assert event_watch.start_due(g)


def test_an_unknown_page_on_a_start_look_has_its_own_wording(watch):
    g = watch(settings=AUTO, cards=("unrecognised", "dh"))
    claim_events.claim_events(g)
    assert g.card_taps() == [0] and not g.settings.flag("EventDecoratedHeroes")
    assert (
        "Decorated Heroes start check: card 1 opened a page that is not recognised (neither "
        "the event's nor another event's)"
    ) in g.lines
    assert g.captures == ["events-unknown-card-1.png"]


def test_event_seen_through_its_bell_turns_the_switch_on_and_claims_at_once(
    watch, monkeypatch, tmp_path
):
    """The card's bell: the switch turned on and the stars claimed in the same visit, even
    with no look for the start due (one just made)."""
    claimed = []
    patch_events(monkeypatch, claimed)
    g = watch(settings=AUTO, bells=(0,), cards=("dh", "basic"))
    event_watch._note_start_look(g)
    assert not event_watch.start_due(g)
    claim_events.claim_events(g)
    assert g.lines[0] == "Events: bell found, opening the events list"
    assert g.openings == 1 and g.card_taps() == [0]
    assert claimed == [0]  # on the event's page, before its X
    assert _saved(tmp_path).flag("EventDecoratedHeroes") and g.beats == [ON_BEAT]
    assert (
        "Decorated Heroes: the event is active in the events list (card 1), switch turned on"
    ) in g.lines
    assert "Events: card 1 is the Decorated Heroes event (switch off)" not in g.lines
    assert g.taps[-1] == atlas.EVENTS_LIST_CLOSE


def test_auto_off_the_bell_path_leaves_the_switch_off(watch, monkeypatch):
    claimed = []
    patch_events(monkeypatch, claimed)
    g = watch(settings={"EventDecoratedHeroes": "0"}, bells=(0,), cards=("dh", "basic"))
    assert not event_watch.start_due(g)
    claim_events.claim_events(g)
    assert claimed == [] and not g.settings.flag("EventDecoratedHeroes") and g.beats == []
    assert "Events: card 1 is the Decorated Heroes event (switch off)" in g.lines


def test_auto_off_never_looks_for_the_start(watch):
    g = watch(settings={"EventDecoratedHeroes": "0"}, cards=("dh",))
    claim_events.claim_events(g)
    assert g.openings == 0 and g.lines == ["Events: no bell on the button, nothing to claim"]
    assert not g.settings.flag("EventDecoratedHeroes")


def test_auto_on_with_the_switch_on_checks_that_the_event_is_still_on(watch):
    """The auto switch changes nothing while the event switch is on: the switch-off check."""
    g = watch(settings={"EventDecoratedHeroesAuto": "1"}, cards=("dh",))
    assert not event_watch.start_due(g) and event_watch.check_due(g)
    claim_events.claim_events(g)
    assert g.openings == 1 and _stays_on(g)
    assert "Decorated Heroes: the event is still in the events list (card 1)" in g.lines


def test_the_switch_turned_off_counts_as_the_days_start_look(watch, now):
    """The absence just confirmed twice: no look for a start at the next cycle."""
    g = watch(settings={"EventDecoratedHeroesAuto": "1"}, cards=("basic",))
    claim_events.claim_events(g)
    assert g.openings == 2 and not g.settings.flag("EventDecoratedHeroes")
    assert g.beats == [GONE_BEAT]
    now[0] += 60_000
    claim_events.claim_events(g)
    assert g.openings == 2 and not event_watch.start_due(g)
    now[0] += event_watch.START_RECHECK_MS
    assert event_watch.start_due(g)


def test_auto_alone_leaves_the_basic_events_bell_alone(watch):
    """Events off, the event switch off, the auto switch on and today's start look made: the
    lit bell of the unclaimed basic events does not open the list at every cycle (review
    2026-09-29); the start looks find the event."""
    g = watch(
        settings={"EventDecoratedHeroes": "0", "Events": "0", "EventDecoratedHeroesAuto": "1"},
        bells=(0,),
        cards=("basic",),
    )
    event_watch._note_start_look(g)
    claim_events.claim_events(g)
    assert g.openings == 0 and g.card_taps() == []
    assert "Events: bell on the button, but basic events are off: nothing to claim" in g.lines
