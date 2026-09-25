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
from firestone_bot.features import decorated_heroes
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


def claim_events(g: Game) -> None:
    """Claim the event rewards. `Events` claims the basic events (Challenges tab); the
    Decorated Heroes switch claims that event's page. Each card with a bell is opened once
    per visit: a card of another kind no longer stops the scan (the Decorated Heroes card,
    active since 2026-09-18, was opened and left at every cycle and hid the cards after it)."""
    basic = g.settings.flag("Events")
    event = daily.event_on(g.settings)
    g.focus()
    if not bells.bell_in(g, g.ms.events_bell):
        g.status("Events: no bell on the button, nothing to claim")
        return
    g.status("Events: bell found, opening the events list")
    # open events
    g.open_screen(g.ms.events_icon, atlas.EVENTS_CLOSE_X)
    total = 0
    opened: set[int] = set()
    for _ in range(MAX_EVENT_VISITS):
        idx = _first_card_with_bell(g, opened)
        if idx is None:
            break
        opened.add(idx)
        g.tap(atlas.EVENTS_CARDS[idx])
        g.wait_still()  # the page scales in
        if decorated_heroes.is_page(g):
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
            g.status(f"Events: card {idx + 1} has no Challenges tab (other event type), skipping")
            g.save_diagnostic(f"events-other-card-{idx + 1}.png")
            g.tap(atlas.EVENTS_PAGE_CLOSE)
    g.tap(atlas.EVENTS_LIST_CLOSE)
    g.toast("Main Menu Check", "Checking to ensure we are on main screen after claiming events", 2)
    main_menu(g)
