"""Port of Functions/ClaimBeer.ahk: tavern beer -> tokens, then tavern tokens and artifact.

Python-only addition: the tavern tokens are played in ONE visit, up to the MaxTokens daily
limit (or until the Play button is no longer green), and the token part is skipped for the
rest of the game day once the limit is reached (see daily.py). The AHK bot played one token
per cycle. The beer -> token purchase itself is kept every cycle, as in AHK.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.features.craft_artifact import craft_artifact
from firestone_bot.features.use_tavern_token import use_token
from firestone_bot.game import Game
from firestone_bot.vision import atlas

MAX_PLAYS_PER_VISIT = 60  # safety when MaxTokens is 0 (unlimited)


def play_tokens(g: Game) -> int:
    """Tavern screen must be open. Plays tokens until the daily limit or no green button."""
    plays = 0
    while plays < MAX_PLAYS_PER_VISIT:
        if daily.tokens_left(g.settings) == 0:
            g.status(f"Tavern: daily token limit reached ({g.settings.MaxTokens})")
            break
        if not use_token(g):
            break
        daily.note_token_used(g.settings)
        plays += 1
        g.status(f"Tavern: token {plays} used ({g.settings.TokenCountDaily} today)")
    return plays


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
    if g.settings.flag("TavernBeerTokens") and g.found(atlas.TAVERN_BEER_CLAIM_READY):
        g.move_to(atlas.TAVERN_BEER_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    big_close(g)
    # check if Use Tavern Token is checked
    if g.settings.flag("Token"):
        if daily.tokens_left(g.settings) == 0:
            g.status("Tavern: daily token limit already reached, skipping tokens")
        else:
            if play_tokens(g) and g.settings.flag("CraftArtifact"):
                craft_artifact(g)
    big_close(g)
