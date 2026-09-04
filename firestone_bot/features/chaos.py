"""Chaos rift from the guild screen (Python rework of subFunctions/Chaos.ahk).

The AHK bot switched the rift to Auto, which spends every available token, including the
paid ones (orange medallion, second counter top right). The rework only hits while the icon
shown inside the green "Hit" button is the FREE token (blue moon, first counter, 10 per day,
refilled about an hour after the daily reset), and stops after MaxChaos hits per game day
(ChaosCountDaily, cleared by the daily reset). The Auto/Manual toggle is never touched.

A hit starts a 3-4 minute battle animation during which the button is grey, but leaving the
rift and reopening it resolves the battle at once (measured 2026-09-04), so the loop closes
and reopens the rift between hits instead of waiting.
"""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.features.chaos_books import buy_books
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _hit_button_token(g: Game) -> str:
    """'free', 'paid' or 'none' depending on the token icon in the Hit button."""
    if g.found(atlas.CHAOS_HIT_ICON_FREE):
        return "free"
    if g.found(atlas.CHAOS_HIT_ICON_PAID):
        return "paid"
    return "none"


def _open_rift(g: Game) -> None:
    g.click_point(atlas.CHAOS_OPEN)  # MouseClick, Left, x, y, 1, 0
    g.sleep(2000)


def hit_chaos(g: Game) -> None:
    need_hits = daily.chaos_left(g.settings) != 0
    need_books = g.settings.flag("ChaosBooks") and not daily.books_done(g.settings)
    if not (need_hits or need_books):
        return  # nothing left for today: the rift is not opened again until the reset
    g.focus()
    # Check for Chaos notification on guild screen
    if not g.found(atlas.CHAOS_DOT):
        return
    _open_rift(g)
    hits = 0
    while need_hits:
        left = daily.chaos_left(g.settings)
        if left == 0:
            g.status(f"Chaos rift: daily limit reached ({g.settings.MaxChaos}), leaving")
            break
        if not g.found(atlas.CHAOS_HIT_READY):
            g.status("Chaos rift: Hit button not ready, leaving")
            break
        token = _hit_button_token(g)
        if token != "free":
            g.status(f"Chaos rift: no free token in the Hit button ({token}), leaving")
            break
        g.move_to(atlas.CHAOS_HIT)
        g.sleep(1000)
        g.click()
        g.sleep(1500)
        daily.note_chaos_hit(g.settings)
        hits += 1
        g.status(f"Chaos rift: hit {hits} ({g.settings.ChaosCountDaily} today)")
        # leave and come back: the battle resolves and the button is green again
        big_close(g)
        _open_rift(g)
    if need_books:
        # once a day, after the hits: buy the books in the rift shop when its bell shows
        buy_books(g)
        daily.note_books_done(g.settings)
    big_close(g)
    if hits:
        g.vars["chaos_hits"] = g.vars.get("chaos_hits", 0) + hits  # runner: guardian upgrades
