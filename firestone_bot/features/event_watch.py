"""Decorated Heroes switch turned off by the bot when the event is over (owner request
2026-09-28: one worry less for the user).

EventDecoratedHeroes raises the tavern / crystal limits and makes the guardian enlightenments;
a user who forgets the switch after the event keeps spending for challenges that no longer
exist. The event's card in the events list is the only sign that it runs: nothing tells the
cards apart without opening them, so the check opens every active card and asks
decorated_heroes.is_page.

Measured 2026-09-28 on the owner's client (1920x1009, new style): the list opens from the
main screen without a bell, its active cards come first in full colour, the upcoming ones
after an "Upcoming events" header in grey (atlas.EVENTS_CARD_STRIPS). The event ends about
2026-10-02 10:00 (its card said "Time left: 3d 15:47" at 18:12), i.e. AT the daily reset.

Wrong verdicts do not cost the same: a false "gone" in the middle of the event loses the
user's event progress, a missed one only keeps today's behaviour. So the switch is turned
off only when two looks, on two separate openings of the list, both saw the list and no
Decorated Heroes page behind any active card; anything unexpected (the list not shown, a card
that opens nothing, a page that does not close back to the list, more active events than the
four modelled slots) gives no verdict and the switch stays on.

When: the events step runs before the shop (the daily reset detection), the town and the
guild, so the check runs in every cycle near the reset (LastTokenReset 23 h old or unknown,
the shop's rule) and the first cycle after the reset turns the switch off before that day's
tavern plays, enlightenments and crystal hits use the event's limits. Otherwise once a game
day (and at each bot start), then every 30 min; never in a visit where claim_events opened
the event's page through its bell (the owner's case: the card's bell stays lit), which
counts as a look. When the page was last seen is kept in memory (Game.vars); the switch is
the only thing written (settings.ini, which the GUI mirrors).
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
POLL_MS = 500
LIST_POLLS = 8  # the list's own X ring, before any read or tap
PAGE_POLLS = 8  # a slow event page: ~6 s with is_page's own pause
EMPTY_READS = 4  # no active card: read again, the cards may show after the list frame
CONFIRM_PAUSE_MS = 3000  # between the two openings of the list
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


def note_seen(g: Game) -> None:
    """The Decorated Heroes page was opened from the events list."""
    g.vars[_seen_key(g)] = _now_ms()


def near_reset(g: Game) -> bool:
    """23 h or more since the last detected daily reset, or none detected (shop.py)."""
    return not 0 < hours_since(g.settings.get("LastTokenReset")) < NEAR_RESET_HOURS


def check_due(g: Game) -> bool:
    """The switch is on and the list should be looked at: the event's page not seen yet this
    game day since the bot started, seen RECHECK_MS ago or more, or the reset is near."""
    if not daily.event_on(g.settings):
        return False
    seen = g.vars.get(_seen_key(g))
    return seen is None or _now_ms() - seen >= RECHECK_MS or near_reset(g)


def colourful_share(img: np.ndarray) -> float:
    """Share of the pixels with a chroma above ACTIVE_CHROMA (an active card's art)."""
    if img.size == 0:
        return 0.0
    px = img[:, :, :3].astype(np.int16)
    return float((px.max(axis=2) - px.min(axis=2) > ACTIVE_CHROMA).mean())


def _list_shown(g: Game) -> bool:
    """The events list is on screen, nothing over it (its own X ring). Count-based polls:
    safe timing and a slow game behave the same."""
    for i in range(LIST_POLLS):
        if g.found(atlas.EVENTS_CLOSE_X):
            return True
        if i < LIST_POLLS - 1:
            g.sleep(POLL_MS)
    return False


def _active_slots(g: Game) -> list[int] | None:
    """Slots whose card is drawn in colour (an active event); None when the list is not
    on screen."""
    if not _list_shown(g):
        return None
    g.wait_still()  # the list scales in
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
    """After a tap on an active card: "dh" (the event's page), "other" (a page over the list
    that is not the event's) or "none" (the list still shows: the tap opened nothing)."""
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
    return "other" if covered else "none"


def _walk(g: Game) -> bool | None:
    """One look through the open list: True = an active card opened the event's page,
    False = no active card is the event (or there is none), None = no verdict (a status line
    says why). Every active card is opened: nothing else tells them apart."""
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
            g.save_diagnostic(f"events-card-{slot + 1}-no-page.png")
            return None
        # another event's page: its X must bring the list back (the event's own page is
        # not closed by it, a pop-up neither)
        g.tap(atlas.EVENTS_PAGE_CLOSE)
        if not _list_shown(g):
            g.status(
                f"Decorated Heroes check: card {slot + 1} opened a page that is not the "
                "event's and the list did not come back"
            )
            g.save_diagnostic(f"events-unknown-card-{slot + 1}.png")
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
    g.status(
        "Decorated Heroes: the event is no longer in the events list (checked twice), "
        "switch turned off"
    )
    g.heartbeat("Decorated Heroes event ended: switch turned off", important=True)


def check_list(g: Game) -> None:
    """The events list is open (claim_events) and the event's page was not seen in this
    visit: look through the active cards; when the event is not there, close the list, wait,
    reopen it and look again; turn the switch off only when both looks agree."""
    first = _walk(g)
    if first is None:
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
        g.status("Decorated Heroes: the second look gave no verdict, the switch stays on")
