"""Port of Functions/ClaimBeer.ahk: tavern beer -> tokens, then tavern tokens and artifact.

Python-only addition: the tavern tokens are played in ONE visit, up to the MaxTokens daily
limit (or until the tavern token counter reads 0), and the token part is skipped for the
rest of the game day once the limit is reached (see daily.py). The AHK bot played one token
per cycle. The beer -> token purchase itself is kept every cycle, as in AHK.

A play counts only when the tavern token counter drops (token_counter, as for the arcane
crystal). A click on a green Play button counted as a play whether the game took a token or
not, so the daily limit and the Decorated Heroes challenge (12 plays) could be reached with
fewer real plays (owner backlog, 2026-09-28). With the counter at 0 the bot leaves without
clicking (whether Play stays green then is not measured). One live play took the counter
from 141 to 140; it read 140 as soon as the round was over, 5.6 s after the Play click
(measured 2026-09-28 on the owner's 1920x1009 Epic client).
"""

from __future__ import annotations

import numpy as np

from firestone_bot import daily
from firestone_bot.features import multiplier, token_counter
from firestone_bot.features.big_close import big_close
from firestone_bot.features.craft_artifact import craft_artifact
from firestone_bot.features.use_tavern_token import use_token
from firestone_bot.game import Game
from firestone_bot.vision import atlas

SCREEN = "Tavern"
MAX_PLAYS_PER_VISIT = 60  # safety when MaxTokens is 0 (unlimited)
TAVERN_TAKEN_MS = 8000  # the drop showed as soon as the round was over; a slow server
TAVERN_RETRIES = 2  # plays the game ignored in one visit before leaving
TAVERN_RETRY_PAUSE_MS = 2000  # a late counter gets a moment before the next play
# plays the counter never showed, per game day: a rect that reads a steady wrong number (a
# window shape the rect misses) must not turn into uncounted plays at every visit
MAX_UNCONFIRMED = 5


def _play_spent(g: Game, count: int | None, before: np.ndarray | None) -> int:
    """Tokens the play took (0: the game did not take one). With the counter read before the
    play, it counts only once the counter reads lower; unreadable, a redraw of the digits'
    pixels is the fallback."""
    if count is not None:
        after = token_counter.wait_drop(g, atlas.TAVERN_TOKEN_DIGITS, count, TAVERN_TAKEN_MS)
        return 0 if after is None else count - after
    changed = g.wait_region_change(
        atlas.TAVERN_TOKEN_DIGITS, before, TAVERN_TAKEN_MS, atlas.ANCHOR_TOP_RIGHT
    )
    return 1 if changed else 0


def _multi_spend(g: Game, n: int) -> None:
    g.status(
        f"Tavern: one play spent {n} tokens, the spend multiplier is not x1: "
        "no more plays until it reads x1"
    )
    g.save_diagnostic("tavern-multiplier.png")
    multiplier.note_multi_spend(g, SCREEN)


def _unconfirmed_key(g: Game) -> str:
    return f"tavern_unconfirmed:{g.settings.get('LastTokenReset')}"


def _day_capped(g: Game) -> bool:
    """True (with a status line) once today's plays the counter never showed reach the cap."""
    if g.vars.get(_unconfirmed_key(g), 0) < MAX_UNCONFIRMED:
        return False
    g.status(
        f"Tavern: {MAX_UNCONFIRMED} plays today not shown on the token counter, "
        "no more plays until the next game day"
    )
    return True


def _count_plays(g: Game, n: int) -> None:
    for _ in range(n):
        daily.note_token_used(g.settings)


def play_tokens(g: Game) -> int:
    """Tavern game screen open: play tokens until the daily limit or the token counter reads
    0, each counted when the counter drops. Returns the number of plays counted."""
    if _day_capped(g):
        return 0
    if not multiplier.ensure_single(g, SCREEN) or multiplier.spend_blocked(g, SCREEN):
        return 0
    plays = 0
    ignored = 0
    ignored_at: int | None = None  # the counter before a play that looked ignored
    unread_saved = False
    while plays < MAX_PLAYS_PER_VISIT:
        if daily.tokens_left(g.settings) == 0:
            g.status(f"Tavern: daily token limit reached ({daily.token_limit(g.settings)})")
            break
        g.move_to(atlas.SPEND_PARK)  # off the Play button and the multiplier
        g.sleep(300)
        count = token_counter.read_stable(g, atlas.TAVERN_TOKEN_DIGITS)
        if ignored_at is not None and count is not None and count < ignored_at:
            # the play that looked ignored took a token, the counter only showed it late
            late, ignored_at = ignored_at - count, None
            ignored = max(0, ignored - 1)
            key = _unconfirmed_key(g)
            g.vars[key] = max(0, g.vars.get(key, 0) - 1)
            _count_plays(g, late)
            plays += late
            g.status(
                f"Tavern: play {plays} confirmed late ({g.settings.TokenCountDaily} today, "
                f"{count} tokens left)"
            )
            if late > 1:
                _multi_spend(g, late)
                break
            continue
        if count == 0:
            g.status("Tavern: no tavern token left, leaving")  # Play would offer to buy some
            break
        if count is None and not unread_saved:
            unread_saved = True
            g.status("Tavern: the token counter is not readable, watching its pixels instead")
            g.save_diagnostic("tavern-counter-unread.png")
        before = None
        if count is None:
            before = g.region_image(atlas.TAVERN_TOKEN_DIGITS, atlas.ANCHOR_TOP_RIGHT)
        if not use_token(g):
            g.status("Tavern: the Play button is not green, no more plays")
            break
        g.move_to(atlas.SPEND_PARK)
        spent = _play_spent(g, count, before)
        if not spent:
            ignored += 1
            ignored_at = count
            key = _unconfirmed_key(g)
            g.vars[key] = g.vars.get(key, 0) + 1
            if ignored > TAVERN_RETRIES:
                g.status("Tavern: the token counter did not go down again, leaving")
            elif not _day_capped(g):
                g.status("Tavern: the token counter did not go down, not counted, trying again")
                g.sleep(TAVERN_RETRY_PAUSE_MS)
                continue
            g.save_diagnostic("tavern-play-not-taken.png")
            break
        ignored_at = None
        _count_plays(g, spent)
        plays += spent
        left = "" if count is None else f", {count - spent} tokens left"
        g.status(f"Tavern: play {plays} ({g.settings.TokenCountDaily} today{left})")
        if spent > 1:
            _multi_spend(g, spent)
            break
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
