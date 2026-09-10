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


MAX_CLOSES = 10  # hard stop when SafetyCap is set, whatever the progress


def find_dialog_x(g: Game, area: tuple[int, int, int, int]) -> blobs.Blob | None:
    """A dialog's close X inside a centre-anchored area: an orange ring holding a cream
    cross. Only a button seen this way is ever clicked (no fixed close point)."""
    rings = blobs.find_blobs(
        g,
        area,
        atlas.DIALOG_RING,
        30,
        anchor=ANCHOR_CENTER,
        min_w=atlas.DIALOG_X_RING_MIN,
        min_h=atlas.DIALOG_X_RING_MIN,
    )
    crosses = blobs.find_blobs(
        g,
        area,
        atlas.DIALOG_X_CROSS,
        30,
        anchor=ANCHOR_CENTER,
        min_w=atlas.DIALOG_X_CROSS_MIN,
        min_h=atlas.DIALOG_X_CROSS_MIN,
    )
    for r in rings:
        if any(r.x1 <= c.cx <= r.x2 and r.y1 <= c.cy <= r.y2 for c in crosses):
            return r
    return None


def _close_rate_popup(g: Game) -> None:
    """The AHK clicked a fixed point whenever a chooser-brown title bar showed; now only the
    X actually found next to it is clicked. The pop-up itself was never captured: a bar
    without an X is logged with a diagnostic so the next one can be measured."""
    x = find_dialog_x(g, atlas.MM_RATE_POPUP_X_AREA)
    if x is None:
        g.status("MainMenu: a brown title bar but no close X next to it, nothing clicked")
        # one capture per cycle: the bar also shows on ordinary screens, and the diagnostics
        # folder keeps only the 40 newest files
        if not g.vars.get("rate_popup_diag"):
            g.vars["rate_popup_diag"] = True
            g.save_diagnostic("rate-popup-no-x.png")
        return
    g.status("MainMenu: closing a pop-up through its X")
    g.tap(Point(x.cx, x.cy, ANCHOR_CENTER), 800)


def main_menu(g: Game) -> bool:
    """Reach the main screen. Returns True when it was recognised (the settings window
    opened by the gear, or the new-style mode button), False at the safety cap.

    SafetyCap counts the closes that changed nothing on screen: from deep inside (the scarab
    market: market, scarab screen, tavern, town) every close removes a layer and is progress,
    and a cap of 3 blind closes gave up one layer short (2026-09-10). MAX_CLOSES still bounds
    the loop."""
    g.focus()
    g.sleep(1000)
    g.focus()
    cap = int(g.settings.get("SafetyCap") or 0)
    closes = stalls = 0
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
            _close_rate_popup(g)
        before = g._thumbnail()
        big_close(g)
        closes += 1
        if not g.changed_since(before):
            stalls += 1
        if closes == 1 and close_chooser(g):
            continue
        if cap and (stalls >= cap or closes >= max(cap, MAX_CLOSES)):
            g.status(f"MainMenu: safety cap reached ({closes} closes, {stalls} without effect)")
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
