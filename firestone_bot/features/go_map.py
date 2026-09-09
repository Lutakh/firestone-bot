"""Open the world map: the Map icon of the main screen, or a keyboard shortcut.

The AHK bot pressed M. On an AZERTY keyboard that key sits elsewhere and the game does not
open the map (Ixyon, 2026-09-09), so the new-style main screen's own Map icon is used by
default and the key is a setting (MapHotkey) for the layouts and interfaces where the icon
is not there.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _hotkey(g: Game) -> str:
    key = (g.settings.get("MapHotkey") or "m").strip()
    return key[:1].lower() or "m"


def _use_icon(g: Game) -> bool:
    mode = (g.settings.get("MapOpen") or "auto").strip().lower()
    if mode == "hotkey" or mode.startswith("key"):
        return False
    if mode.startswith("icon"):
        return True
    return g.style == "new"  # auto: the icon only exists on the new main screen


def _open_once(g: Game) -> None:
    if _use_icon(g):
        g.tap(atlas.NS_MAP_ICON, 0)
    else:
        g.key(_hotkey(g))


def go_map(g: Game) -> None:
    g.focus()
    g.toast("Open Map", "Opening the map window", 1.5)
    _open_once(g)
    if g.fast():
        g.sleep(g.CHANGE_SETTLE_MS)
        if not g.wait_for(atlas.DIALOG_CLOSE_X):
            g.status("Open Map: the map did not appear, trying once more")
            _open_once(g)
            g.sleep(g.CHANGE_SETTLE_MS)
            if not g.wait_for(atlas.DIALOG_CLOSE_X):
                g.save_diagnostic("map-not-opened.png")
        g.wait_still()
    else:
        g.sleep(1500)
