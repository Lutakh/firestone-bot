"""Port of Functions/subFunctions/OraclesGift.ahk and MysteryBox.ahk (same code, different
signature colour and variation). The open-button rows sit lower than for chests."""

from __future__ import annotations

from firestone_bot.features.open_chest_type import close_chest_dialog
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Probe


def _open_gift(g: Game, title: str, color: int, variation: int) -> None:
    # Scroll to the bottom to look for the gift
    g.move_to(atlas.BAG_SCROLL_HOVER)
    g.toast(title, "Scrolling to ensure bottom gifts are visible", 1.5)
    g.wheel(-5)
    hit = g.search(Probe(*g.ms.chest_grid, color, variation, f"gift_{color:06X}"))
    if hit is None:
        return
    g.tap_screen(hit.sx, hit.sy)
    target = None
    for probe, button in atlas.GIFT_OPEN_BUTTONS:
        if g.found(probe):
            target = button
            break
    if target is not None:
        g.tap(target, 0)
        g.sleep(10000)  # long delay in case 10 or more are opened
        for _ in range(5):
            if g.found(atlas.CHEST_OPEN_MORE_READY, variation=3):
                g.tap(atlas.CHEST_OPEN_MORE, 10000)
            else:
                break  # Goto, ...Close
            g.sleep(100)
    # ...Close:
    close_chest_dialog(g)


def oracles_gift(g: Game) -> None:
    _open_gift(g, "Oracle's Gift", atlas.ORACLE_GIFT_COLOR, 1)


def mystery_box(g: Game) -> None:
    _open_gift(g, "Mystery Box", atlas.MYSTERY_BOX_COLOR, 2)
