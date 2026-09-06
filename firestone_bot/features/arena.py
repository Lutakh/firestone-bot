"""Port of Functions/Arena.ahk + subFunctions/ArenaBattle.ahk: five Arena of Kings battles
against a random opponent column. Called by the runner at most every 6 hours."""

from __future__ import annotations

import random

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def arena_battle(g: Game) -> bool:
    """Wait (unbounded, like AHK) for the battle's claim button, click it, return True."""
    cap = int(g.settings.get("SafetyCap") or 0)
    waited_ms = 0
    while True:  # Wait:
        if g.found(atlas.ARENA_BATTLE_DONE):
            g.tap(atlas.ARENA_BATTLE_CLAIM, 1000)
            return True
        step = 2000 if not g.fast() else g.poll_ms()
        g.sleep(step)
        waited_ms += step
        if cap and waited_ms >= cap * 2000:  # the cap counts AHK iterations of 2 s
            g.status(f"ArenaBattle: safety cap of {cap} iterations reached")
            return True


def arena(g: Game) -> None:
    g.focus()
    # open battles
    g.tap(atlas.TOWN_BATTLES)
    # choose arena of kings
    g.tap(atlas.ARENA_OF_KINGS)
    random_x = random.choice(atlas.ARENA_OPPONENT_COLUMNS)
    g.sleep(6000)
    for _ in range(5):
        # refresh opponents
        g.tap(atlas.ARENA_REFRESH, 3000)
        # choose random opponent
        g.tap_xy(random_x, atlas.ARENA_OPPONENT_Y, 1000)
        # check for buy more battles popup
        if g.found(atlas.ARENA_BUY_MORE):
            big_close(g)
            big_close(g)
            daily.note_arena_done(g.settings)  # no battles left today
            return
        g.tap(atlas.ARENA_FIGHT, 0)
        while not arena_battle(g):
            g.sleep(5000)
    big_close(g)
    daily.note_arena_done(g.settings)  # skip the arena until the next daily reset
