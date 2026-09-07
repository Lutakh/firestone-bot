"""Chest icons of the new-style bag, told apart by their whole icon rather than one colour.

The AHK bot finds a chest by a signature colour (PixelSearch, variation 1). In the new
adventure style the icons share their palettes: on the owner's Windows client (2026-09-07)
the Uncommon signature sat closer to the Golden jewel chest than to the Uncommon chest, the
Common one to the Emerald chest, Opal was 24 levels off its icon, and most others needed a
variation of 2 to 3 where a false positive was 3 to 5 away. Here each slot of the chest
grid is compared with reference thumbnails (chest_refs.py): an 8x8 grid of mean colours
over a 96 logical px window centred on the slot, the window slid by a few px around the
centre (the grid shifts slightly with its row count) and the best position kept. Self
distance is under 3 levels, the nearest other chest is 19 levels away; the count digits
(bottom right of a slot) are left out of the comparison. The grid is captured once per
scan (one grab, 15 slots, 25 positions each).
"""

from __future__ import annotations

import numpy as np

from firestone_bot.vision import chest_refs
from firestone_bot.vision.atlas import Point

# slot centres (logical): three columns, five rows
CELL_COLS = (1595, 1720, 1845)
CELL_ROWS = (216, 341, 461, 576, 701)
WINDOW = 96  # logical px, the icon with a little margin
OFFSETS = (-8, -4, 0, 4, 8)  # logical px, slid around the slot centre
MAX_DISTANCE = 10.0  # mean levels: a match must be this close...
MAX_RATIO = 0.5  # ...and this much closer than the runner-up
_MARGIN = WINDOW // 2 + max(OFFSETS)
GRID_RECT = (
    CELL_COLS[0] - _MARGIN,
    CELL_ROWS[0] - _MARGIN,
    CELL_COLS[-1] + _MARGIN,
    CELL_ROWS[-1] + _MARGIN,
)

_MASK = np.ones((chest_refs.THUMB, chest_refs.THUMB), bool)
_MASK[5:, 4:] = False  # the count digits
_REFS = {
    name: np.array(v, dtype=float).reshape(chest_refs.THUMB, chest_refs.THUMB, 3)
    for name, v in chest_refs.REFS.items()
}


def known(name: str) -> bool:
    return name in _REFS


def thumbnail(img: np.ndarray) -> np.ndarray:
    """8x8 mean colours of an RGB image of any size (blocks of equal share)."""
    n = chest_refs.THUMB
    h, w = img.shape[:2]
    ys = np.linspace(0, h, n + 1).astype(int)
    xs = np.linspace(0, w, n + 1).astype(int)
    out = np.empty((n, n, 3), dtype=float)
    for i in range(n):
        for j in range(n):
            out[i, j] = img[ys[i] : ys[i + 1], xs[j] : xs[j + 1]].mean(axis=(0, 1))
    return out


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b)[_MASK].mean())


def classify_thumbnails(thumbs: list[np.ndarray]) -> tuple[str | None, float, float]:
    """(name, distance, runner-up distance) for a slot seen at several offsets; name is
    None when nothing is close enough ('_empty' for an empty slot)."""
    best: dict[str, float] = {}
    for t in thumbs:
        for name, ref in _REFS.items():
            d = distance(t, ref)
            if d < best.get(name, 1e9):
                best[name] = d
    ranked = sorted(best.items(), key=lambda kv: kv[1])
    name, d = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 1e9
    if d > MAX_DISTANCE or d > MAX_RATIO * second:
        return None, d, second
    return name, d, second


class GridImage:
    """One RGB capture of the whole chest grid, sliced per slot in logical coordinates."""

    def __init__(self, g) -> None:
        self.img = g.region_image(GRID_RECT)[:, :, ::-1]  # BGR capture -> RGB references
        x1, y1, x2, y2 = GRID_RECT
        self.fx = self.img.shape[1] / (x2 - x1)  # capture px per logical px
        self.fy = self.img.shape[0] / (y2 - y1)
        self.x1, self.y1 = x1, y1

    def window(self, cx: int, cy: int) -> np.ndarray:
        half = WINDOW // 2
        xa = int((cx - half - self.x1) * self.fx)
        xb = int((cx + half - self.x1) * self.fx)
        ya = int((cy - half - self.y1) * self.fy)
        yb = int((cy + half - self.y1) * self.fy)
        return self.img[ya:yb, xa:xb]

    def classify(self, cx: int, cy: int) -> tuple[str | None, float, float]:
        thumbs = [thumbnail(self.window(cx + dx, cy + dy)) for dy in OFFSETS for dx in OFFSETS]
        return classify_thumbnails(thumbs)


def classify_cell(g, cx: int, cy: int) -> tuple[str | None, float, float]:
    return GridImage(g).classify(cx, cy)


def scan_grid(g) -> dict[tuple[int, int], str | None]:
    """What each slot of the chest grid holds: chest name, '_empty' or None (unknown)."""
    grid = GridImage(g)
    return {
        (c, r): grid.classify(cx, cy)[0]
        for r, cy in enumerate(CELL_ROWS)
        for c, cx in enumerate(CELL_COLS)
    }


def find_chest(g, name: str) -> Point | None:
    """Centre of the slot holding `name`, None when the bag has none."""
    grid = GridImage(g)
    for cy in CELL_ROWS:
        for cx in CELL_COLS:
            if grid.classify(cx, cy)[0] == name:
                return Point(cx, cy)
    return None
