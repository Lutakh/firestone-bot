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

from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.vision import atlas

MAX_EVENT_VISITS = 6  # rescans of the list; each visit handles one card with a bell


def _claim_challenges(g: Game) -> int:
    claimed = 0
    for probe, button in atlas.EVENTS_CHALLENGE_CLAIMS:
        if g.found(probe):
            g.move_to(button)
            g.sleep(1000)
            g.click()
            g.sleep(1500)
            claimed += 1
    return claimed


def _first_card_with_bell(g: Game) -> int | None:
    for i, bell in enumerate(atlas.EVENTS_CARD_BELLS):
        if g.found(bell):
            return i
    return None


def claim_events(g: Game) -> None:
    g.focus()
    if not g.found(atlas.EVENTS_BELL):
        return
    # open events
    g.move_to(atlas.EVENTS_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    total = 0
    for _ in range(MAX_EVENT_VISITS):
        idx = _first_card_with_bell(g)
        if idx is None:
            break
        g.move_to(atlas.EVENTS_CARDS[idx])
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        if g.found(atlas.EVENTS_CHALLENGES_TAB_BELL):
            g.move_to(atlas.EVENTS_CHALLENGES_TAB)
            g.sleep(1000)
            g.click()
            g.sleep(1500)
            n = _claim_challenges(g)
            total += n
            g.status(f"Events: card {idx + 1}, {n} challenge reward(s) claimed")
            g.move_to(atlas.EVENTS_PAGE_CLOSE)
            g.sleep(1000)
            g.click()
            g.sleep(1500)
            if n == 0:
                break  # bell but nothing green: avoid looping on the same card
        else:
            g.status(f"Events: card {idx + 1} has no Challenges tab (other event type), skipping")
            g.move_to(atlas.EVENTS_PAGE_CLOSE)
            g.sleep(1000)
            g.click()
            g.sleep(1500)
            break
    g.move_to(atlas.EVENTS_LIST_CLOSE)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    g.toast("Main Menu Check", "Checking to ensure we are on main screen after claiming events", 2)
    main_menu(g)
