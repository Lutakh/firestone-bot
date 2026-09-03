"""Port of Functions/subFunctions/OraclesGift.ahk and MysteryBox.ahk (same code, different
signature colour and variation). The open-button rows sit lower than for chests."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Probe


def _open_gift(g: Game, title: str, color: int, variation: int) -> None:
    # Scroll to the bottom to look for the gift
    g.move_to(atlas.BAG_SCROLL_HOVER)
    g.toast(title, "Scrolling to ensure bottom gifts are visible", 1.5)
    g.wheel(-5)
    hit = g.search(Probe(*atlas.CHEST_GRID, color, variation, f"gift_{color:06X}"))
    if hit is None:
        return
    g.move_screen(hit.sx, hit.sy)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    target = None
    for probe, button in atlas.GIFT_OPEN_BUTTONS:
        if g.found(probe):
            target = button
            break
    if target is not None:
        g.move_to(target)
        g.sleep(1000)
        g.click()
        g.sleep(10000)  # long delay in case 10 or more are opened
        for _ in range(5):
            if g.found(atlas.CHEST_OPEN_MORE_READY, variation=3):
                g.move_to(atlas.CHEST_OPEN_MORE)
                g.sleep(1000)
                g.click()
                g.sleep(10000)
            else:
                break  # Goto, ...Close
            g.sleep(100)
    # ...Close:
    big_close(g)
    # failsafe in case big close opens options
    g.move_to(atlas.CHEST_FAILSAFE)
    g.sleep(1000)
    g.click()
    g.sleep(1000)


def oracles_gift(g: Game) -> None:
    _open_gift(g, "Oracle's Gift", atlas.ORACLE_GIFT_COLOR, 1)


def mystery_box(g: Game) -> None:
    _open_gift(g, "Mystery Box", atlas.MYSTERY_BOX_COLOR, 2)
