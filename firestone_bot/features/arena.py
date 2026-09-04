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
    n = 0
    while True:  # Wait:
        if g.found(atlas.ARENA_BATTLE_DONE):
            g.move_to(atlas.ARENA_BATTLE_CLAIM)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
            return True
        g.sleep(2000)
        n += 1
        if cap and n >= cap:
            g.status(f"ArenaBattle: safety cap of {cap} iterations reached")
            return True


def arena(g: Game) -> None:
    g.focus()
    # open battles
    g.move_to(atlas.TOWN_BATTLES)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    # choose arena of kings
    g.move_to(atlas.ARENA_OF_KINGS)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    random_x = random.choice(atlas.ARENA_OPPONENT_COLUMNS)
    g.sleep(6000)
    for _ in range(5):
        # refresh opponents
        g.move_to(atlas.ARENA_REFRESH)
        g.sleep(1000)
        g.click()
        g.sleep(3000)
        # choose random opponent
        g.move(random_x, atlas.ARENA_OPPONENT_Y)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        # check for buy more battles popup
        if g.found(atlas.ARENA_BUY_MORE):
            big_close(g)
            big_close(g)
            daily.note_arena_done(g.settings)  # no battles left today
            return
        g.move_to(atlas.ARENA_FIGHT)
        g.sleep(1000)
        g.click()
        while not arena_battle(g):
            g.sleep(5000)
    big_close(g)
    daily.note_arena_done(g.settings)  # skip the arena until the next daily reset
