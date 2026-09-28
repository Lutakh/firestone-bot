"""Port of Functions/subFunctions/UseTavernToken.ahk: play one tavern card at random.

Returns True when the green Play button was clicked and a round played (Play, a random card,
dismiss; about 5 s, measured 2026-09-28), False when Play is not green. A green Play does not
mean a token was taken: the caller checks the tavern token counter (claim_beer.play_tokens)."""

from __future__ import annotations

import random

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def use_token(g: Game) -> bool:
    # check for use token button
    if not g.found(atlas.TAVERN_USE_TOKEN_READY):
        return False
    g.tap(atlas.TAVERN_USE_TOKEN, 1000)
    card = random.choice(atlas.TAVERN_CARDS)
    g.sleep(1000)
    g.tap(card, 1000)
    # random click in case "get game tokens" was clicked
    g.tap(atlas.TAVERN_DISMISS, 1000)
    return True
