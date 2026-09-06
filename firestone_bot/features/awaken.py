"""Port of Functions/subFunctions/Awaken.ahk: awaken heroes from the guild screen, picking
the highest affordable multiplier, then switching to auto."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def awaken_run(g: Game) -> None:
    g.focus()
    # Check for awaken heroes notification on guild screen
    if not g.found(atlas.AWAKEN_DOT):
        return
    g.heartbeat("AwakenRun (Improved): found notif", important=True)
    g.tap(atlas.AWAKEN_OPEN)
    # First check that the Awaken Button Is Enabled
    g.tap(atlas.AWAKEN_X1, 1000)
    if g.found(atlas.AWAKEN_BUTTON_ORANGE):
        for probe, button in atlas.AWAKEN_MULTIPLIERS:  # x160 .. x1
            if g.found(probe):
                g.tap(button, 1000)
                if g.found(atlas.AWAKEN_AUTO_READY):
                    break  # Goto, Automatic
        # Automatic:
        g.heartbeat("AwakenRun: auto button")
        g.tap(atlas.AWAKEN_AUTO, 20000)
    elif g.found(atlas.AWAKEN_BUTTON_GREEN):
        g.tap(atlas.AWAKEN_BUTTON, 3000)
    big_close(g)
