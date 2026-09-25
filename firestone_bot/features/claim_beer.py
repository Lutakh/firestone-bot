"""Port of Functions/ClaimBeer.ahk: tavern beer -> tokens, then tavern tokens and artifact.

Python-only addition: the tavern tokens are played in ONE visit, up to the MaxTokens daily
limit (or until the Play button is no longer green), and the token part is skipped for the
rest of the game day once the limit is reached (see daily.py). The AHK bot played one token
per cycle. The beer -> token purchase itself is kept every cycle, as in AHK.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features import multiplier
from firestone_bot.features.big_close import big_close
from firestone_bot.features.craft_artifact import craft_artifact
from firestone_bot.features.use_tavern_token import use_token
from firestone_bot.game import Game
from firestone_bot.vision import atlas

MAX_PLAYS_PER_VISIT = 60  # safety when MaxTokens is 0 (unlimited)


def play_tokens(g: Game) -> int:
    """Tavern screen must be open. Plays tokens until the daily limit or no green button."""
    plays = 0
    if not multiplier.ensure_single(g, "Tavern"):
        return 0
    while plays < MAX_PLAYS_PER_VISIT:
        if daily.tokens_left(g.settings) == 0:
            g.status(f"Tavern: daily token limit reached ({daily.token_limit(g.settings)})")
            break
        if not use_token(g):
            break
        daily.note_token_used(g.settings)
        plays += 1
        g.status(f"Tavern: token {plays} used ({g.settings.TokenCountDaily} today)")
    return plays


def claim_beer(g: Game) -> None:
    # check if skip beer was selected (the Decorated Heroes event still needs its plays)
    event = daily.event_on(g.settings)
    # tavern skipped by the user: the event visits it only for its plays, nothing else
    forced = g.settings.flag("Beer")
    if forced and (not event or daily.tokens_left(g.settings) == 0):
        return
    g.focus()
    # open Tavern
    g.require_screen(atlas.TOWN_TAVERN, atlas.TAVERN_CLOSE_X, 1000, via_town=True)
    g.tap(atlas.TAVERN_BEER_TAB, 1000)
    # check for enough beer to claim tokens
    g.tap(atlas.TAVERN_TOKEN_SHOP, 1000)
    buy = g.settings.flag("TavernBeerTokens") and not forced
    if buy and g.found(atlas.TAVERN_BEER_CLAIM_READY):
        g.tap(atlas.TAVERN_BEER_CLAIM, 1000)
    big_close(g)
    # check if Use Tavern Token is checked
    if g.settings.flag("Token") or event:
        if daily.tokens_left(g.settings) == 0:
            g.status("Tavern: daily token limit already reached, skipping tokens")
        else:
            play_tokens(g)
    # Rework: the craft button is checked on every visit (AHK only after a token was played,
    # so a ready artifact waited until the next token; owner 2026-09-07)
    if g.settings.flag("CraftArtifact") and not forced:
        craft_artifact(g)
    big_close(g)
