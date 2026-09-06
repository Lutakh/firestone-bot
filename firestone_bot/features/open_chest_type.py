"""Port of Functions/subFunctions/OpenChestType.ahk.

Finds a chest of the given signature colour in the bag's chest grid, clicks it (the FOUND
pixel, not a fixed point), then opens with the largest available "open N" button, repeating up
to 5 times.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Probe


def _click_equip(g: Game) -> bool:
    """Click "equip" if it is there. Returns True when it was."""
    if g.found(atlas.CHEST_EQUIP_READY):
        g.tap(atlas.CHEST_EQUIP, 1000)
        return True
    return False


def close_chest_dialog(g: Game) -> None:
    """Close the chest / gift dialog. New style: its own X (BigClose would hit the bag panel's
    X); classic: BigClose plus the AHK failsafe."""
    if g.ms.chest_dialog_close is not None:
        g.tap(g.ms.chest_dialog_close)
        return
    # OpenChestTypeClose:
    big_close(g)
    # failsafe in case big close opens options
    g.tap(atlas.CHEST_FAILSAFE, 1000)


def open_chest_type(g: Game, color: int, variation: int = 2) -> None:
    hit = g.search(Probe(*g.ms.chest_grid, color, variation, f"chest_{color:06X}"))
    if hit is None:
        return
    g.tap_screen(hit.sx, hit.sy)  # MouseMove, FoundX, FoundY
    # pick the largest open button: 11-50, then 2-10, then 1
    target = None
    for probe, button in atlas.CHEST_OPEN_BUTTONS:
        if g.found(probe):
            target = button
            break
    if target is None:
        # NoOpenButton:
        g.toast("Open Chests", "No Open Button Available", 1.5)
        close_chest_dialog(g)
        return
    g.tap(target, 0)
    g.sleep(10000)  # long delay in case 10 or more chests are opened
    _click_equip(g)
    for _ in range(5):
        if g.found(atlas.CHEST_OPEN_MORE_READY):
            # click 50 or however many are left
            g.tap(atlas.CHEST_OPEN_MORE, 10000)
            if not _click_equip(g):
                break  # Goto, OpenChestTypeClose
    close_chest_dialog(g)
