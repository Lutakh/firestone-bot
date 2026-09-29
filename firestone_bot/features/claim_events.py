"""Events: claim the challenge rewards of every active event (rework of ClaimEvents.ahk).

Layout measured 2026-09-04: the Events button is at the bottom left of the main screen with a
bell when something is claimable. The events list shows the active events first (one card per
event, a bell on the card when it has something to claim), then the upcoming ones greyed out.
Inside an event, the "Events" / "Challenges" tabs sit at the top; the Challenges tab carries a
bell and its page lists up to three challenges, each with a green Claim button in the same
column (the AHK probes/points still match this layout). Events without those two tabs are a
different kind and are skipped.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features import decorated_heroes, event_watch
from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells

MAX_EVENT_VISITS = 6  # rescans of the list; each visit handles one card with a bell


def _claim_challenges(g: Game) -> int:
    claimed = 0
    for probe, button in atlas.EVENTS_CHALLENGE_CLAIMS:
        if g.found(probe):
            g.tap(button)
            claimed += 1
    return claimed


def _first_card_with_bell(g: Game, skip: set[int] = frozenset()) -> int | None:
    for i, bell in enumerate(atlas.EVENTS_CARD_BELLS):
        if i in skip:
            continue
        # counted, not probed: the card bell is a red sprite whose exact shade drifts with the
        # canvas scale (it missed the RED_DOT probe at 2560x1302 on macOS, 2026-09-09)
        if bells.bell_in(g, bell):
            return i
    return None


def _other_card_diagnostic(g: Game, idx: int) -> None:
    # once per game day and card: the same card with a lit bell and nothing on its
    # Challenges tab was captured at every cycle (~1000 a day, 2026-09-18..25)
    key = f"events_other_card:{idx}:{g.settings.get('LastTokenReset')}"
    if not g.vars.get(key):
        g.vars[key] = 1
        g.save_diagnostic(f"events-other-card-{idx + 1}.png")


def claim_events(g: Game) -> None:
    """Claim the event rewards. `Events` claims the basic events (Challenges tab); the
    Decorated Heroes switch claims that event's page. Each card with a bell is opened once
    per visit: a card of another kind no longer stops the scan (the Decorated Heroes card,
    active since 2026-09-18, was opened and left at every cycle and hid the cards after it).
    With the switch on, the list is also opened without a bell when the event's presence is
    due a check (event_watch): the bot turns the switch off once the event is not active.
    With the switch off and EventDecoratedHeroesAuto on, it is opened when a look for the
    event's start is due, and the event's page, seen that way or through its bell, turns the
    switch on (owner request 2026-09-29); through the bell, its challenges are claimed in the
    same visit. The runner calls this again right after a shop visit that detected the daily
    reset, where the new game day makes either look due (the event starts and ends at the
    reset)."""
    basic = g.settings.flag("Events")
    event = daily.event_on(g.settings)
    auto = event_watch.auto_on(g.settings)
    g.focus()
    check = event_watch.check_due(g)
    start = event_watch.start_due(g)
    # The bell opens the list only for what claims there. With the auto switch alone, the
    # basic events stay unclaimed and their bell stays lit: the list was opened at every
    # cycle for weeks between two events (review 2026-09-29). The start looks find the event.
    lit = bells.bell_in(g, g.ms.events_bell)
    if lit and (basic or event):
        g.status("Events: bell found, opening the events list")
    elif check:
        g.status(
            "Events: no bell on the button, opening the events list to check that the "
            "Decorated Heroes event is still on"
        )
    elif start:
        g.status(
            "Events: no bell on the button, opening the events list to see whether the "
            "Decorated Heroes event has started"
        )
    elif lit:
        g.status("Events: bell on the button, but basic events are off: nothing to claim")
        return
    else:
        g.status("Events: no bell on the button, nothing to claim")
        return
    # open events
    g.open_screen(g.ms.events_icon, atlas.EVENTS_CLOSE_X)
    total = 0
    seen = False  # the Decorated Heroes page, opened through its card's bell
    opened: set[int] = set()
    for _ in range(MAX_EVENT_VISITS):
        idx = _first_card_with_bell(g, opened)
        if idx is None:
            break
        opened.add(idx)
        g.tap(atlas.EVENTS_CARDS[idx])
        g.wait_still()  # the page scales in
        if decorated_heroes.is_page(g):
            seen = True
            event_watch.note_seen(g)
            if not event and auto:
                event_watch.switch_on(g, idx)
                event = True  # its challenges are claimed right away
            if event and decorated_heroes.open_challenges(g):
                total += decorated_heroes.claim_page(g)
            elif event:
                g.status("Events: the Decorated Heroes challenges did not show")
                g.save_diagnostic("decorated-heroes-page.png")
            else:
                g.status(f"Events: card {idx + 1} is the Decorated Heroes event (switch off)")
            g.tap(atlas.DH_PAGE_CLOSE)
            continue
        if not basic:
            g.tap(atlas.EVENTS_PAGE_CLOSE)
            continue
        if bells.bell_in(g, atlas.EVENTS_CHALLENGES_TAB_BELL):
            g.tap(atlas.EVENTS_CHALLENGES_TAB)
            n = _claim_challenges(g)
            total += n
            g.status(f"Events: card {idx + 1}, {n} challenge reward(s) claimed")
            if n == 0:
                # A bell with no green Claim is normal (a new event, nothing finished yet),
                # but it is also what a mis-measured claim probe looks like on another
                # client: keep the page so the three rows can be checked.
                g.save_diagnostic("events-no-claim.png")
            g.tap(atlas.EVENTS_PAGE_CLOSE)
        else:
            # the tab is there (owner captures 2026-09-26/27): its bell is not, the card's
            # bell is for something else on the page
            g.status(f"Events: card {idx + 1}, no bell on its Challenges tab, nothing to claim")
            _other_card_diagnostic(g, idx)
            g.tap(atlas.EVENTS_PAGE_CLOSE)
    if check and not seen:
        event_watch.check_list(g)
    elif start and not seen and not daily.event_on(g.settings):
        event_watch.look_for_start(g)
    g.tap(atlas.EVENTS_LIST_CLOSE)
    g.toast("Main Menu Check", "Checking to ensure we are on main screen after claiming events", 2)
    main_menu(g)
