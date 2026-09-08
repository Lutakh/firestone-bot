"""Port of Functions/subFunctions/OpenChestType.ahk.

Finds a chest of the given signature colour in the bag's chest grid, clicks it (the FOUND
pixel, not a fixed point), then opens with the largest available "open N" button, repeating up
to 5 times.

New style (2026-09-07): opening plays an animation (5.5 s for one chest, longer for fifty)
during which nothing is clickable; the AHK 10 s sleep was not enough and the bot went on
clicking through the loot screen. The end of the animation is waited for instead: the
"open more" buttons and the result screen's X only draw once it ended.
"""

from __future__ import annotations

import time

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, chest_grid
from firestone_bot.vision.atlas import Point, Probe


def _click_equip(g: Game) -> bool:
    """Click "equip" if it is there. Returns True when it was."""
    if g.found(atlas.CHEST_EQUIP_READY):
        g.tap(atlas.CHEST_EQUIP, 1000)
        return True
    return False


def wait_chest_animation(g: Game) -> bool:
    """Wait for the opening animation to end. Classic style: the AHK 10 s sleep. New style:
    poll for the result screen (open-more buttons or its X), up to CHEST_ANIMATION_TIMEOUT_MS;
    a timeout keeps a diagnostic capture and returns False."""
    probes = g.ms.chest_result_ready
    if not probes:
        g.sleep(10000)  # long delay in case 10 or more chests are opened
        return True
    g.sleep(1000)  # the dialog's buttons stay a moment after the click
    end = time.monotonic() + atlas.CHEST_ANIMATION_TIMEOUT_MS / 1000
    while time.monotonic() < end:
        if any(g.found(p) for p in probes):
            g.wait_still()
            return True
        g.sleep(250)
    g.status("Open Chests: the opening animation did not end in time")
    g.save_diagnostic("chest-animation.png")
    return False


def close_chest_dialog(g: Game) -> None:
    """Close the chest / gift dialog. New style: its own X (BigClose would hit the bag panel's
    X), or the result screen's X when the loot is on screen; classic: BigClose plus the AHK
    failsafe."""
    if g.ms.chest_result_close is not None and g.found(atlas.NS_CHEST_RESULT_CLOSE_X):
        g.tap(g.ms.chest_result_close, 1000)
        return
    if g.ms.chest_dialog_close is not None:
        g.tap(g.ms.chest_dialog_close)
        return
    # OpenChestTypeClose:
    big_close(g)
    # failsafe in case big close opens options
    g.tap(atlas.CHEST_FAILSAFE, 1000)


def _open_more_available(g: Game, variation: int | None) -> bool:
    """The "open more" button, given a moment to draw: the result screen's X shows before
    its buttons slide in, and a check right after the X read "no chest left" with 47 in
    stock (Windows, 2026-09-07). Without stock the screen has no button at all."""
    end = time.monotonic() + 1.5
    while True:
        if g.found(g.ms.chest_open_more_ready, variation=variation):
            return True
        if time.monotonic() >= end:
            return False
        g.sleep(200)


def open_more_loop(g: Game, variation: int | None = None) -> None:
    """On the result screen: click "open more" (x50, or what is left) up to five times, each
    time waiting for the animation; stop when the button is gone (no chest left) or, in the
    classic style, when nothing was equipped."""
    for _ in range(5):
        if not _open_more_available(g, variation):
            break
        g.tap(g.ms.chest_open_more, 0)
        if not wait_chest_animation(g):
            break
        if g.ms.chest_result_close is None and not _click_equip(g):
            break  # Goto, OpenChestTypeClose


def _click_chest(g: Game, name: str | None, color: int, variation: int) -> bool:
    """Click the chest in the bag grid: by its icon in the new style when a reference is
    known (chest_grid), else by the AHK signature colour. False when the bag has none."""
    if g.style == "new" and name is not None and chest_grid.known(name):
        # a hovered icon grows (and pushes its neighbours): read the grid with the pointer away
        g.move_to(atlas.NS_MODE_PARK)
        g.sleep(300)
        at = chest_grid.find_chest(g, name)
        if at is None:
            return False
        g.tap(at, 1000)
        return True
    hit = g.search(Probe(*g.ms.chest_grid, color, variation, f"chest_{color:06X}"))
    if hit is None:
        return False
    g.tap_screen(hit.sx, hit.sy)  # MouseMove, FoundX, FoundY
    return True


def find_open_buttons(g: Game) -> list[Point]:
    """Centres of the green buttons in the dialog's button row (new style), left to right.
    The row holds x1 / x10 / x50, or fewer when the stock is small (x1 / x3 for three
    Lunar chests, 2026-09-08: the fixed x50 point fell beside the x3 button)."""
    from firestone_bot.vision.probes import match_mask

    x1, y1, x2, y2 = atlas.NS_CHEST_BUTTON_ROW
    img = g.region_image((x1, y1, x2, y2))
    green = match_mask(img, atlas.GREEN_BUTTON, 3)
    cols = green.mean(axis=0) > 0.3
    fx = (x2 - x1) / cols.shape[0]
    out: list[Point] = []
    start = None
    for i, on in enumerate(list(cols) + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if (i - start) * fx >= atlas.NS_CHEST_BUTTON_MIN_W:
                out.append(Point(x1 + int((start + i) / 2 * fx), (y1 + y2) // 2))
            start = None
    return out


def open_chest_type(g: Game, color: int, variation: int = 2, name: str | None = None) -> None:
    if not _click_chest(g, name, color, variation):
        return
    # pick the largest open button: 11-50, then 2-10, then 1
    target = None
    if g.style == "new":
        g.wait_still()
        buttons = find_open_buttons(g)
        target = buttons[-1] if buttons else None
    else:
        for probe, button in g.ms.chest_open_buttons:
            if g.found(probe):
                target = button
                break
    if target is None:
        # NoOpenButton:
        g.toast("Open Chests", "No Open Button Available", 1.5)
        close_chest_dialog(g)
        return
    g.tap(target, 0)
    if wait_chest_animation(g):
        g.vars["chests_opened"] = g.vars.get("chests_opened", 0) + 1
        _click_equip(g)
        open_more_loop(g)
    close_chest_dialog(g)
