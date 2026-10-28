"""Port of Functions/Arena.ahk + subFunctions/ArenaBattle.ahk: five Arena of Kings battles
against a random opponent column. Called by the runner at most every 6 hours."""

from __future__ import annotations

import random

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game, ScreenNotReached
from firestone_bot.vision import atlas

BATTLE_MAX_MS = 180_000  # a battle takes about 30 s (owner: 5 battles in 2 min 18 s)


def arena_battle(g: Game) -> bool:
    """Wait for the battle's claim button and click it (True). A claim button that never
    shows within SafetyCap x 20 s (BATTLE_MAX_MS at most, also with SafetyCap 0) ends the
    arena with a capture: the AHK waited forever, then tapped on blind (review 2026-10-28:
    the battle result was never seen on a client taller than 16:9)."""
    cap = int(g.settings.get("SafetyCap") or 0)
    limit = min(cap * 20000, BATTLE_MAX_MS) if cap else BATTLE_MAX_MS
    waited_ms = 0
    while True:  # Wait:
        if g.found(atlas.ARENA_BATTLE_DONE):
            g.tap(atlas.ARENA_BATTLE_CLAIM, 1000)
            return True
        step = 2000 if not g.fast() else g.poll_ms()
        g.sleep(step)
        waited_ms += step
        if waited_ms >= limit:
            g.status(f"ArenaBattle: no claim button after {limit // 1000} s, arena left")
            g.save_diagnostic("arena-battle-miss.png")
            raise ScreenNotReached("arena battle result")


def arena(g: Game) -> None:
    g.focus()
    g.status("Arena: opening the battles building")
    g.require_screen(atlas.TOWN_BATTLES, atlas.BATTLES_CLOSE_X, via_town=True)
    # choose arena of kings (a greyed card opens nothing: the step is then skipped)
    g.status("Arena: opening the Arena of Kings")
    g.tap(atlas.ARENA_OF_KINGS, expect=atlas.ARENA_CLOSE_X)
    if g.found(atlas.MESSAGE_CLOSE_X):
        # "Unlocks once you acquire at least 2 war machines." (2026-09-08): not today
        g.status("Arena: not available yet (game message), skipped until the next game day")
        g.tap(atlas.MESSAGE_CLOSE, 800)
        big_close(g)
        daily.note_arena_done(g.settings)
        return
    if g.fast() and not g.found(atlas.ARENA_CLOSE_X):
        g.save_diagnostic("arena-miss.png")  # what was on screen instead (owner, 2026-09-08)
        raise ScreenNotReached("arena of kings")
    random_x = random.choice(atlas.ARENA_OPPONENT_COLUMNS)
    g.sleep(6000)
    for _ in range(5):
        # refresh opponents
        g.tap(atlas.ARENA_REFRESH, 3000)
        # choose random opponent
        g.tap_xy(random_x, atlas.ARENA_OPPONENT_Y, 1000, atlas.ANCHOR_CENTER)
        # check for buy more battles popup (read once it has scaled in)
        g.wait_still()
        if g.found(atlas.ARENA_BUY_MORE):
            big_close(g)
            big_close(g)
            daily.note_arena_done(g.settings)  # no battles left today
            return
        g.status("Arena: starting a battle")
        g.tap(atlas.ARENA_FIGHT, 0)
        while not arena_battle(g):
            g.sleep(5000)
    big_close(g)
    daily.note_arena_done(g.settings)  # skip the arena until the next daily reset
