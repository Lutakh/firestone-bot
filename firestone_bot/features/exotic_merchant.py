"""Port of Functions/ExoticMerchant.ahk: sell exotic items, then upgrades and chest purchases.

The Sell buttons are found by colour (2026-09-10): the AHK clicked fixed points that assumed
one aspect ratio and one scroll position, and at 3024x1675 none of its probes matched. The list
is scrolled to one end until it stops moving, every button (grey or green) is found, and the
buttons are named row by row from that end with atlas.EXOTIC_GRID. A view that does not look
like the list end (the wrong number of buttons in the end row) is not clicked at all.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from firestone_bot.features.big_close import big_close
from firestone_bot.features.buy_exotic import buy_exotic
from firestone_bot.features.exotic_upgrades import exotic_upgrades
from firestone_bot.game import Game
from firestone_bot.vision import atlas, blobs
from firestone_bot.vision.atlas import Point

MAX_SELLS_PER_ITEM = 60
SCROLL_STEP = 15
SCROLL_TRIES = 10

_GR, _GG, _GB = (
    (atlas.GREEN_BUTTON >> 16) & 255,
    (atlas.GREEN_BUTTON >> 8) & 255,
    atlas.GREEN_BUTTON & 255,
)


def _any_button(px: np.ndarray) -> np.ndarray:
    """Pixels of a Sell button, sold out (grey) or not (bright green, and its dark green top
    band): the whole button makes one blob either way."""
    r, g, b = (px[..., i].astype(int) for i in range(3))
    grey = (abs(r - g) < 14) & (abs(g - b) < 14) & (r >= 90) & (r <= 175)
    v = atlas.EXOTIC_GREEN_VAR
    green = (abs(r - _GR) <= v) & (abs(g - _GG) <= v) & (abs(b - _GB) <= v)
    dark_green = (g > r + 40) & (g > b + 30) & (g < 140)
    return grey | green | dark_green


@dataclass(frozen=True)
class Button:
    cx: int
    cy: int
    green: bool  # something to sell


def button_rows(g: Game) -> list[list[Button]]:
    """Every Sell button on screen, grouped in rows top to bottom, each row left to right."""
    whole = blobs.find_blobs(
        g,
        atlas.EXOTIC_LIST,
        mask_fn=_any_button,
        anchor=atlas.ANCHOR_CENTER,
        min_w=atlas.EXOTIC_BUTTON_MIN_W,
        min_h=atlas.EXOTIC_BUTTON_MIN_H,
    )
    green = blobs.find_blobs(
        g,
        atlas.EXOTIC_LIST,
        atlas.GREEN_BUTTON,
        atlas.EXOTIC_GREEN_VAR,
        anchor=atlas.ANCHOR_CENTER,
        min_w=atlas.EXOTIC_BUTTON_MIN_W // 2,
        min_h=atlas.EXOTIC_BUTTON_MIN_H // 2,
    )
    rows: list[list[Button]] = []
    for b in sorted(whole, key=lambda b: b.cy):
        is_green = any(b.x1 <= q.cx <= b.x2 and b.y1 <= q.cy <= b.y2 for q in green)
        button = Button(b.cx, b.cy, is_green)
        if rows and abs(rows[-1][0].cy - b.cy) < atlas.EXOTIC_ROW_TOLERANCE:
            rows[-1].append(button)
        else:
            rows.append([button])
    return [sorted(r, key=lambda b: b.cx) for r in rows]


def name_buttons(rows: list[list[Button]], from_bottom: bool) -> list[tuple[str, Button]] | None:
    """Name the buttons of a view scrolled to the top (or the bottom) of the list. None when the
    end row does not have the grid's number of buttons: then the view is not the list end and
    no name can be trusted. Rows that are not complete (cut by the list edge) are left out."""
    grid = atlas.EXOTIC_GRID
    if not rows:
        return None
    end = rows[-1] if from_bottom else rows[0]
    if len(end) != len(grid[-1] if from_bottom else grid[0]):
        return None
    offset = len(grid) - len(rows) if from_bottom else 0
    named = []
    for i, row in enumerate(rows):
        r = offset + i
        if 0 <= r < len(grid) and len(row) == len(grid[r]):
            named += list(zip(grid[r], row, strict=True))
    return named


def _scroll_to_end(g: Game, up: bool) -> bool:
    """Wheel until the list stops moving (it scrolls with inertia: a fixed number of notches
    stopped short of the bottom at 3024x1675)."""
    for _ in range(SCROLL_TRIES):
        before = g.region_image(atlas.EXOTIC_LIST).astype(int)
        g.move_to(atlas.EXOTIC_LIST_HOVER)
        g.sleep(200)
        g.wheel(SCROLL_STEP if up else -SCROLL_STEP)
        g.sleep(700)
        g.wait_still()
        after = g.region_image(atlas.EXOTIC_LIST).astype(int)
        if before.shape == after.shape and float(abs(before - after).mean()) < 1.0:
            return True
    return False


def _sell_view(g: Game, wanted: set[str], sold: Counter, from_bottom: bool) -> None:
    """Click the green buttons of the wanted items until none is left in this view. The
    pointer is parked before each look: a hovered button is a lighter green."""
    while True:
        g.move_to(atlas.EXOTIC_PARK)
        g.sleep(300)
        named = name_buttons(button_rows(g), from_bottom)
        if named is None:
            g.status("Exotic merchant: the sell list does not look as expected, nothing clicked")
            g.save_diagnostic("exotic-sell-unknown.png")
            return
        target = next(
            ((n, b) for n, b in named if b.green and n in wanted and sold[n] < MAX_SELLS_PER_ITEM),
            None,
        )
        if target is None:
            return
        name, b = target
        g.tap(Point(b.cx, b.cy, atlas.ANCHOR_CENTER), 800)
        g.wait_still()
        sold[name] += 1


def sell(g: Game, wanted: set[str]) -> Counter:
    """Sell every copy of the wanted items (AHK sold one per visit, owner 2026-09-08)."""
    sold: Counter = Counter()
    for from_bottom in (False, True):
        if not _scroll_to_end(g, up=not from_bottom):
            g.status("Exotic merchant: the sell list kept moving, this end skipped")
            continue
        _sell_view(g, wanted, sold, from_bottom)
    for name, n in sold.items():
        g.status(f"Exotic merchant: {name} sold {n} time(s)")
    return sold


def wants_visit(g: Game) -> bool:
    """The visit is only worth it after a chest was opened this cycle (Game.vars): selling
    the loot is what brings the coins the upgrades and chest purchases are paid with
    (owner, 2026-09-08)."""
    if g.vars.get("chests_opened", 0):
        return True
    g.status("Exotic merchant: no chest opened this cycle, visit skipped")
    return False


def exotic_merchant(g: Game) -> None:
    # Open exotic merchant
    g.require_screen(atlas.TOWN_EXOTIC_MERCHANT, atlas.DIALOG_CLOSE_X, via_town=True)
    s = g.settings
    sells = s.flag("SellScrolls") or s.flag("SellAll") or s.flag("SellNoGold")
    if sells and g.vars.get("chests_opened", 0):
        wanted = set(atlas.EXOTIC_SCROLLS)
        if s.flag("SellAll"):
            wanted |= atlas.EXOTIC_GOLD | atlas.EXOTIC_ITEMS
        elif s.flag("SellNoGold"):
            wanted |= atlas.EXOTIC_ITEMS
        sell(g, wanted)
    # ExChecks:
    if s.flag("ExoticUpgrades"):
        exotic_upgrades(g)
    if s.flag("BuyEx") and not g.locked("emblem_chests"):
        buy_exotic(g)
    big_close(g)
