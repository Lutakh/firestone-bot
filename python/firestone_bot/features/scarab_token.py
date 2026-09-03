"""Port of Functions/subFunctions/ScarabToken.ahk: claim the Pharaoh's token in the tavern."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def scarab_token(g: Game) -> None:
    g.toast("Scarab's Token", "Claiming Scarab's Token", 2)
    g.focus()
    # open Tavern
    g.move_to(atlas.TOWN_TAVERN)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    if g.found(atlas.SCARAB_GAME_DOT):
        # Open Scarab's Game
        g.move_to(atlas.TAVERN_SCARAB_TAB)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        if g.found(atlas.SCARAB_TOKEN_DOT):
            g.move_to(atlas.SCARAB_TOKEN_TAB)
            g.sleep(1000)
            g.click()
            g.sleep(1500)
            # claim Pharaoh's Token
            g.move_to(atlas.SCARAB_TOKEN_CLAIM)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
            big_close(g)
    big_close(g)
