"""Port of Functions/ClaimEvents.ahk: claim the three challenge rewards of the top event."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.main_menu import main_menu
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_events(g: Game) -> None:
    g.focus()
    if not g.found(atlas.EVENTS_RED_DOT):
        return
    # open events
    g.move_to(atlas.EVENTS_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # click top event
    g.move_to(atlas.EVENTS_TOP_EVENT)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # click challenges
    g.move_to(atlas.EVENTS_CHALLENGES_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # claim 3 challenges
    for probe, button in atlas.EVENTS_CHALLENGE_CLAIMS:
        if g.found(probe):
            g.move_to(button)
            g.sleep(1000)
            g.click()
            g.sleep(500)
    big_close(g)
    big_close(g)
    g.toast("Main Menu Check", "Checking to ensure we are on main screen after claiming events", 2)
    main_menu(g)
