"""Port of Functions/ClaimBeer.ahk: tavern beer -> tokens, then tavern token and artifact.

Python-only addition: the daily token limit (MaxTokens setting, see daily.py). One cycle uses
at most one token, like the AHK bot; the limit only stops the bot once TokenCountDaily reaches
MaxTokens, until the next daily reset.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.features.craft_artifact import craft_artifact
from firestone_bot.features.use_tavern_token import use_token
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def claim_beer(g: Game) -> None:
    # check if skip beer was selected
    if g.settings.flag("Beer"):
        return
    g.focus()
    # open Tavern
    g.move_to(atlas.TOWN_TAVERN)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    g.move_to(atlas.TAVERN_BEER_TAB)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # check for enough beer to claim tokens
    g.move_to(atlas.TAVERN_TOKEN_SHOP)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    if g.found(atlas.TAVERN_BEER_CLAIM_READY):
        g.move_to(atlas.TAVERN_BEER_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    big_close(g)
    # check if Use Tavern Token is checked
    if g.settings.flag("Token"):
        left = daily.tokens_left(g.settings)
        if left == 0:
            g.status(f"Tavern: daily token limit reached ({g.settings.MaxTokens}), skipping")
        else:
            if use_token(g):
                daily.note_token_used(g.settings)
                g.status(f"Tavern: token used ({g.settings.TokenCountDaily} today)")
            craft_artifact(g)
    big_close(g)
