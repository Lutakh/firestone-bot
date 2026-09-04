"""Port of Functions/subFunctions/UseTavernToken.ahk: play one tavern card at random.

Returns True when a token was actually used (the daily token limit relies on it)."""

from __future__ import annotations

import random

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def use_token(g: Game) -> bool:
    # check for use token button
    if not g.found(atlas.TAVERN_USE_TOKEN_READY):
        return False
    g.move_to(atlas.TAVERN_USE_TOKEN)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    card = random.choice(atlas.TAVERN_CARDS)
    g.sleep(1000)
    g.move_to(card)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # random click in case "get game tokens" was clicked
    g.move_to(atlas.TAVERN_DISMISS)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    return True
