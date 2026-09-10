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
from firestone_bot.vision import atlas, blobs
from firestone_bot.vision.atlas import ANCHOR_CENTER, Point


def _settings_blue(px):
    """The settings buttons' blue (a gradient 0x0987FF..0x3687FF), BGR capture pixels."""
    b, g, r = (px[..., i].astype(int) for i in range(3))
    return (b > 200) & (r < 110) & (g > 90) & (g < 180)


def settings_open(g: Game) -> bool:
    """Whether the settings window is on screen: its row of blue buttons, or the old
    one-pixel probe (kept: it is right at 1920x1080 and 2560x1302)."""
    row = blobs.find_blobs(
        g,
        atlas.SETTINGS_BUTTON_ROW,
        mask_fn=_settings_blue,
        anchor=ANCHOR_CENTER,
        min_w=atlas.SETTINGS_BUTTON_MIN_W,
        min_h=atlas.SETTINGS_BUTTON_MIN_H,
    )
    return len(row) >= atlas.SETTINGS_BUTTONS_MIN or g.found(atlas.MM_SETTINGS_OPEN)


def close_settings(g: Game) -> None:
    """Classic style: close the settings window with its own X, then the gear as before if
    it is still there (the gear toggles it)."""
    g.tap(atlas.SETTINGS_CLOSE, 800)
    if settings_open(g):
        big_close(g)


def main_menu(g: Game) -> bool:
    """Reach the main screen. Returns True when it was recognised (the settings window
    opened by the gear, or the new-style mode button), False at the safety cap."""
    g.focus()
    g.sleep(1000)
    g.focus()
    cap = int(g.settings.get("SafetyCap") or 0)
    n = 0
    from firestone_bot.vision import layouts

    while True:  # SettingsFinder:
        if g.style == "new" and layouts.on_new_main_screen(g):
            return True
        if settings_open(g):
            # The settings window only opens from the main screen: close it and we are home.
            # New adventure style: it has its own X (BigClose would only hit the gear again);
            # the style may still be wrong at the first cycle, so the other X is tried too.
            if g.style == "new":
                g.tap(atlas.NS_OPTIONS_CLOSE)
                if g.found(atlas.MM_SETTINGS_OPEN):
                    big_close(g)
            else:
                close_settings(g)
            return True
        if g.found(atlas.MM_RATE_POPUP):
            g.tap(atlas.MM_RATE_POPUP_CLOSE)
        big_close(g)
        n += 1
        if n == 1 and close_chooser(g):
            continue
        if cap and n >= cap:
            g.status(f"MainMenu: safety cap of {cap} iterations reached")
            return False


CHOOSER_CLOSE_PROBES = (atlas.MESSAGE_CLOSE_X, atlas.TAVERN_CLOSE_X, atlas.ENGINEER_CLOSE_X)


def close_chooser(g: Game) -> bool:
    """Close what the big X of the main menu cannot: a centred building chooser (tavern,
    battles, engineer: it dims the town, whose X does not answer under it) or the bag
    panel (its own X on the panel; 2026-09-08: a bag left open by a stopped run blocked
    every step of the next one). True when something was closed."""
    for probe in CHOOSER_CLOSE_PROBES:
        if g.found(probe):
            g.tap(Point(probe.x2 + 20, (probe.y1 + probe.y2) // 2, ANCHOR_CENTER), 800)
            return True
    if g.found(g.ms.bag_close_x):
        g.tap(g.ms.bag_close, 800)
        return True
    return False
