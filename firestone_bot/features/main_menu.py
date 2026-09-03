"""Port of Functions/subFunctions/MainMenu.ahk.

Makes sure we are on the main screen: the BigClose position is the settings gear on the main
screen, so clicking it opens the settings window; once that window is detected, one more
BigClose leaves us on the main screen. A rate-the-game pop-up is dismissed on the way.

AHK `Send, !{Tab}` + `WinActivate` becomes a plain window activation (plan 3.2).
The loop is unbounded in AHK; `SafetyCap` (Python-only setting, default 0 = off) can cap it.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def main_menu(g: Game) -> None:
    g.focus()
    g.sleep(1000)
    g.focus()
    cap = int(g.settings.get("SafetyCap") or 0)
    n = 0
    while True:  # SettingsFinder:
        if g.found(atlas.MM_SETTINGS_OPEN):
            big_close(g)
            return
        if g.found(atlas.MM_RATE_POPUP):
            g.move_to(atlas.MM_RATE_POPUP_CLOSE)
            g.sleep(1000)
            g.click()
            g.sleep(1500)
        big_close(g)
        n += 1
        if cap and n >= cap:
            g.status(f"MainMenu: safety cap of {cap} iterations reached")
            return
