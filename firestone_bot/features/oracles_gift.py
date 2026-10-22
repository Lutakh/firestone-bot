"""Port of Functions/subFunctions/OraclesGift.ahk and MysteryBox.ahk (same code, different
signature colour and variation). The open-button rows sit lower than for chests, and
lower still in the latest game version: the buttons are located, not clicked at fixed
points."""

from __future__ import annotations

from firestone_bot.features.open_chest_type import (
    close_chest_dialog,
    open_more_loop,
    wait_chest_animation,
)
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Point, Probe
from firestone_bot.vision.buttons import green_buttons


def _open_gift(g: Game, title: str, color: int, variation: int) -> None:
    # Scroll to the bottom to look for the gift
    g.move_to(atlas.BAG_SCROLL_HOVER)
    g.toast(title, "Scrolling to ensure bottom gifts are visible", 1.5)
    g.wheel(-5)
    hit = g.search(Probe(*g.ms.chest_grid, color, variation, f"gift_{color:06X}"))
    if hit is None:
        return
    g.tap_screen(hit.sx, hit.sy)
    target = _open_button(g)
    if target is None:
        g.toast(title, "No Open Button Available", 1.5)
    else:
        g.tap(target, 0)
        if wait_chest_animation(g):
            open_more_loop(g, variation=3)
    # ...Close:
    close_chest_dialog(g)


def _open_button(g: Game) -> Point | None:
    """The largest open button of the gift dialog: the rightmost green button of its row
    (x1 / x10 / x50), found wherever the row sits; the AHK points when none is found."""
    g.wait_still()  # the dialog has scaled in
    # variation 10: nothing else in the dialog is green, and colours drift a few levels in
    # some captures (a Mac's colour profile; Qualitas's video needed 6)
    # read and clicked centre-anchored like the dialog: per-corner anchors stretched the
    # row on ultrawide clients and the button fell under GIFT_BUTTON_MIN_W
    buttons = green_buttons(
        g,
        atlas.GIFT_BUTTON_ROW,
        min_w=atlas.GIFT_BUTTON_MIN_W,
        variation=10,
        anchor=atlas.ANCHOR_CENTER,
    )
    if buttons:
        return buttons[-1]
    for probe, button in atlas.GIFT_OPEN_BUTTONS:
        if g.found(probe):
            return button
    return None


def oracles_gift(g: Game) -> None:
    _open_gift(g, "Oracle's Gift", atlas.ORACLE_GIFT_COLOR, 1)


def mystery_box(g: Game) -> None:
    _open_gift(g, "Mystery Box", atlas.MYSTERY_BOX_COLOR, 2)
