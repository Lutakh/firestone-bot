"""Port of Functions/subFunctions/ScarabToken.ahk: claim the Pharaoh's token in the tavern."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def scarab_token(g: Game) -> None:
    if not g.settings.flag("ScarabTokenClaim"):
        return
    g.toast("Scarab's Token", "Claiming Scarab's Token", 2)
    g.focus()
    # open Tavern
    g.tap(atlas.TOWN_TAVERN, 1000, expect=atlas.TAVERN_CLOSE_X)
    if g.found(atlas.SCARAB_GAME_DOT):
        # Open Scarab's Game
        g.tap(atlas.TAVERN_SCARAB_TAB, 1000)
        if g.found(atlas.SCARAB_TOKEN_DOT):
            g.tap(atlas.SCARAB_TOKEN_TAB)
            # claim Pharaoh's Token
            g.tap(atlas.SCARAB_TOKEN_CLAIM, 1000)
            big_close(g)
    big_close(g)
