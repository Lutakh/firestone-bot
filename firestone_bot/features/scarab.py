"""Port of Functions/Scarab.ahk: use a scarab token in the tavern game."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def scarab(g: Game) -> None:
    # check if skip using scarab token was selected
    if g.settings.flag("Scarab"):
        return
    g.focus()
    # open Tavern
    g.move_to(atlas.TOWN_TAVERN)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    g.move_to(atlas.TAVERN_SCARAB_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    if g.found(atlas.TAVERN_USE_TOKEN_READY):
        g.move_to(atlas.TAVERN_USE_TOKEN)
        g.sleep(1000)
        g.click()
        g.sleep(10000)
    big_close(g)
