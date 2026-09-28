"""Decorated Heroes switch turned off by the bot when the event is not active (owner request
2026-09-28: one worry less for the user).

EventDecoratedHeroes raises the tavern / crystal limits and makes the guardian enlightenments;
a user who forgets the switch after the event keeps spending for challenges that no longer
exist. The event's card in the events list is the only sign that it runs: nothing tells the
cards apart without opening them, so the check opens every active card and asks
decorated_heroes.is_page. A switch turned on before the event starts goes off the same way
(the coming event's card is grey and never opened): the status says the event is not
active, not that it ended.

Measured 2026-09-28 on the owner's client (1920x1009, new style): the list opens from the
main screen without a bell, its active cards come first in full colour, the upcoming ones
after an "Upcoming events" header in grey (atlas.EVENTS_CARD_STRIPS). The event ends about
2026-10-02 10:00 (its card said "Time left: 3d 15:47" at 18:12), i.e. AT the daily reset.
The list scrolls and the game reopens a screen as it was left (the map keeps its offset, a
page its last tab): each look wheels the list back to its top before reading it (review
2026-09-28: left scrolled down, it shows only the header and grey cards, which read as
"gone" while the event's card sits above the view).

Wrong verdicts do not cost the same: a false "gone" in the middle of the event loses the
user's event progress, a missed one only keeps today's behaviour. So the switch is turned
off only when two looks, on two separate openings of the list, both saw the list and no
Decorated Heroes page behind any active card, every page opened being positively another
event's (its own X ring, atlas.EVENTS_PAGE_CLOSE_X). Anything unexpected gives no verdict and
the switch stays on: the list not shown, a card that opens nothing, a page recognised as
neither (a Decorated Heroes page that is_page misses on another client may close on the
other pages' X too, review 2026-09-28), a page that does not close back to the list, more
active events than the four modelled slots.

When: the events step runs before the shop (the daily reset detection), the town and the
guild, so the check runs in every cycle near the reset (LastTokenReset 23 h old or unknown,
the shop's rule). LastTokenReset is when the shop detected the reset, not the reset itself:
after a bot started hours after a reset, that window comes hours late. So the runner also
runs the events step right after a shop visit that detected the reset; the new game day
makes the check due, and the first cycle of the day turns the switch off before its tavern
plays, enlightenments and crystal hits use the event's limits. Otherwise once a game day
(and at each bot start), then every 30 min; never in a visit where claim_events opened the
event's page through its bell (the owner's case: the card's bell stays lit), which counts as
a look. A look without a verdict is retried at the next cycle, then waits 30 min like a
sighting (every cycle still near the reset), and its captures are kept once a game day: a
list that never gives one (four other active events, a card that opens nothing) was opened,
walked and captured at every cycle (review 2026-09-28). What was seen is kept in memory
(Game.vars); the switch is the only thing written (settings.ini, which the GUI mirrors).
"""

from __future__ import annotations

import time

import numpy as np

from firestone_bot import daily
from firestone_bot.features import decorated_heroes
from firestone_bot.game import Game
from firestone_bot.state import hours_since
from firestone_bot.vision import atlas

RECHECK_MS = 30 * 60 * 1000  # a look at the list while the event's page is not seen
NEAR_RESET_HOURS = 23  # from then on, a look at every cycle (the shop's rule)
NO_VERDICT_LOOKS = 2  # looks without a verdict at consecutive cycles, then RECHECK_MS apart
POLL_MS = 500
LIST_POLLS = 8  # the list's own X ring, before any read or tap
PAGE_POLLS = 8  # a slow event page: ~6 s with is_page's own pause
EMPTY_READS = 4  # no active card: read again, the cards may show after the list frame
CONFIRM_PAUSE_MS = 3000  # between the two openings of the list
# Wheel-up notches over the list: back to its top from wherever it was left (a few upcoming
# events past the four slots); nothing moves when it is there already. The shop wheels its
# deals back the same way.
TOP_NOTCHES = 20
# Colourful = a chroma (max - min channel) above 80: the lavender header bars and list
# background reach 64 at most; share of a card band: active 0.44, upcoming grey card 0.067.
ACTIVE_CHROMA = 80
ACTIVE_SHARE_MIN = 0.25
OTHER_PAGE_POLLS = 2  # covered list + the basic page's X ring this often: not the event


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _seen_key(g: Game) -> str:
    # per game day: a new day (LastTokenReset changed by the shop) always looks once
    return f"dh_seen:{g.settings.get('LastTokenReset')}"


def _no_verdict_key(g: Game) -> str:
    # per game day: (looks without a verdict since the last verdict, when the last one was)
    return f"dh_no_verdict:{g.settings.get('LastTokenReset')}"


def note_seen(g: Game) -> None:
    """The Decorated Heroes page was opened from the events list."""
    g.vars[_seen_key(g)] = _now_ms()
    g.vars.pop(_no_verdict_key(g), None)  # a verdict: a later miss is retried at once


def _note_no_verdict(g: Game) -> None:
    count, _ = g.vars.get(_no_verdict_key(g), (0, 0))
    g.vars[_no_verdict_key(g)] = (count + 1, _now_ms())


def near_reset(g: Game) -> bool:
    """23 h or more since the last detected daily reset, or none detected (shop.py)."""
    return not 0 < hours_since(g.settings.get("LastTokenReset")) < NEAR_RESET_HOURS


def check_due(g: Game) -> bool:
    """The switch is on and the list should be looked at: always near the reset; otherwise
    unless the event's page was seen less than RECHECK_MS ago this game day, or the last
    NO_VERDICT_LOOKS looks gave no verdict, the last one less than RECHECK_MS ago."""
    if not daily.event_on(g.settings):
        return False
    if near_reset(g):
        return True
    now = _now_ms()
    seen = g.vars.get(_seen_key(g))
    if seen is not None and now - seen < RECHECK_MS:
        return False
    misses, last = g.vars.get(_no_verdict_key(g), (0, 0))
    return misses < NO_VERDICT_LOOKS or now - last >= RECHECK_MS


def colourful_share(img: np.ndarray) -> float:
    """Share of the pixels with a chroma above ACTIVE_CHROMA (an active card's art)."""
    if img.size == 0:
        return 0.0
    px = img[:, :, :3].astype(np.int16)
    return float((px.max(axis=2) - px.min(axis=2) > ACTIVE_CHROMA).mean())


def _diagnostic_once(g: Game, name: str) -> None:
    # once per game day and name: a list without a verdict is looked at again at every
    # cycle near the reset (as claim_events._other_card_diagnostic)
    key = f"dh_capture:{name}:{g.settings.get('LastTokenReset')}"
    if not g.vars.get(key):
        g.vars[key] = 1
        g.save_diagnostic(name)


def _list_shown(g: Game) -> bool:
    """The events list is on screen, nothing over it (its own X ring). Count-based polls:
    safe timing and a slow game behave the same."""
    for i in range(LIST_POLLS):
        if g.found(atlas.EVENTS_CLOSE_X):
            return True
        if i < LIST_POLLS - 1:
            g.sleep(POLL_MS)
    return False


def _to_top(g: Game) -> None:
    """Wheel the list back to its top: the strips and the card taps are measured on its
    first four slots, and the game reopens the list where it was left."""
    g.move_to(atlas.EVENTS_CARDS[1])  # the wheel scrolls what is under the pointer
    g.sleep(300)
    g.wheel(TOP_NOTCHES)  # positive = WheelUp
    g.sleep(500)
    g.wait_still()  # the list scrolls with inertia


def _active_slots(g: Game) -> list[int] | None:
    """Slots whose card is drawn in colour (an active event), the list at its top; None
    when the list is not on screen."""
    if not _list_shown(g):
        return None
    g.wait_still()  # the list scales in
    _to_top(g)
    g.move_to(decorated_heroes.PAGE_PARK)  # the header above the first card: a hovered card
    g.sleep(300)  # may be drawn lighter
    for i in range(EMPTY_READS):
        active = [
            slot
            for slot, rect in enumerate(atlas.EVENTS_CARD_STRIPS)
            if colourful_share(g.region_image(rect, atlas.ANCHOR_CENTER)) >= ACTIVE_SHARE_MIN
        ]
        if active or i == EMPTY_READS - 1:
            return active
        g.sleep(POLL_MS)
    return []


def _page_kind(g: Game) -> str:
    """After a tap on an active card: "dh" (the event's page), "other" (another event's
    page, recognised by its own X ring), "unknown" (a page over the list recognised as
    neither) or "none" (the list still shows: the tap opened nothing)."""
    covered = 0
    for i in range(PAGE_POLLS):
        if decorated_heroes.is_page(g):
            return "dh"
        if g.found(atlas.EVENTS_CLOSE_X):
            covered = 0
        else:
            covered += 1
            if covered >= OTHER_PAGE_POLLS and g.found(atlas.EVENTS_PAGE_CLOSE_X):
                return "other"
        if i < PAGE_POLLS - 1:
            g.sleep(POLL_MS)
    return "unknown" if covered else "none"


def _walk(g: Game) -> bool | None:
    """One look through the open list: True = an active card opened the event's page,
    False = no active card is the event (or there is none), None = no verdict (a status line
    says why). Every active card is opened: nothing else tells them apart."""
    g.focus()  # another window over the game would read as a list without active cards
    active = _active_slots(g)
    if active is None:
        g.status("Decorated Heroes check: the events list is not on screen")
        return None
    for slot in active:
        if not _list_shown(g):
            g.status("Decorated Heroes check: the events list is not on screen")
            return None
        g.tap(atlas.EVENTS_CARDS[slot])
        g.wait_still()  # the page scales in
        kind = _page_kind(g)
        if kind == "dh":
            g.tap(atlas.DH_PAGE_CLOSE)
            note_seen(g)
            g.status(f"Decorated Heroes: the event is still in the events list (card {slot + 1})")
            return True
        if kind == "none":
            g.status(f"Decorated Heroes check: card {slot + 1} opened nothing")
            _diagnostic_once(g, f"events-card-{slot + 1}-no-page.png")
            return None
        if kind == "unknown":
            # not the event's page as far as is_page can tell, not another event's either:
            # no verdict, whether or not the other pages' X closes it
            _diagnostic_once(g, f"events-unknown-card-{slot + 1}.png")  # the page itself
            g.tap(atlas.EVENTS_PAGE_CLOSE)
            if _list_shown(g):
                g.status(
                    f"Decorated Heroes check: card {slot + 1} opened a page that is not "
                    "recognised (neither the event's nor another event's)"
                )
            else:
                g.status(
                    f"Decorated Heroes check: card {slot + 1} opened a page that is not the "
                    "event's and the list did not come back"
                )
            return None
        # another event's page: its X must bring the list back (the event's own page is
        # not closed by it, a pop-up neither)
        g.tap(atlas.EVENTS_PAGE_CLOSE)
        if not _list_shown(g):
            g.status(
                f"Decorated Heroes check: card {slot + 1} opened a page that is not the "
                "event's and the list did not come back"
            )
            _diagnostic_once(g, f"events-unknown-card-{slot + 1}.png")
            return None
    if len(active) == len(atlas.EVENTS_CARDS):
        g.status("Decorated Heroes check: every card slot holds an active event, more may follow")
        return None
    return False


def _switch_off(g: Game) -> None:
    g.save_diagnostic("decorated-heroes-gone.png")  # the list as the bot saw it
    # the runner's shared Settings: the GUI switch follows (Binder.refresh_from_settings),
    # the same path as RestartGameTest in runner.py
    g.settings.set("EventDecoratedHeroes", "0")
    g.settings.save()
    # "not active", not "ended": the switch may have been turned on before the event starts
    g.status(
        "Decorated Heroes: the event is not active in the events list (checked twice), "
        "switch turned off"
    )
    g.heartbeat("Decorated Heroes event not active: switch turned off", important=True)


def check_list(g: Game) -> None:
    """The events list is open (claim_events) and the event's page was not seen in this
    visit: look through the active cards; when the event is not there, close the list, wait,
    reopen it and look again; turn the switch off only when both looks agree."""
    first = _walk(g)
    if first is None:
        _note_no_verdict(g)
        g.status("Decorated Heroes: no verdict from the events list, the switch stays on")
        return
    if first:
        return
    g.status("Decorated Heroes: not in the events list, reopening it to look once more")
    g.tap(atlas.EVENTS_LIST_CLOSE)
    g.sleep(CONFIRM_PAUSE_MS)
    g.open_screen(g.ms.events_icon, atlas.EVENTS_CLOSE_X)
    second = _walk(g)
    if second is False:
        _switch_off(g)
    elif second is None:
        _note_no_verdict(g)
        g.status("Decorated Heroes: the second look gave no verdict, the switch stays on")
