"""Colour blobs: connected areas of pixels near a colour inside a logical rect, returned as
logical bounding boxes (2026-09-08, for the research tree nodes and the like).

Connectivity is computed on a coarse grid of cells (a few logical px each) so the search
stays numpy-only and takes a few milliseconds on a 4K capture; a cell counts when at least
`fill` of its pixels match. Boxes are therefore rounded outwards to the cell size, which is
fine for widgets tens of px wide.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from firestone_bot.platform import capture
from firestone_bot.platform.window import Rect
from firestone_bot.vision.atlas import Anchor


@dataclass(frozen=True)
class Blob:
    """Logical bounding box (x2, y2 exclusive) and the number of matching pixels."""

    x1: int
    y1: int
    x2: int
    y2: int
    pixels: int

    @property
    def cx(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        return (self.y1 + self.y2) // 2

    @property
    def w(self) -> int:
        return self.x2 - self.x1

    @property
    def h(self) -> int:
        return self.y2 - self.y1


def colour_mask(img: np.ndarray, color: int, variation: int) -> np.ndarray:
    """Pixels of a BGR image within `variation` of an 0xRRGGBB colour on every channel."""
    a = img.astype(int)
    cr, cg, cb = (color >> 16) & 255, (color >> 8) & 255, color & 255
    return (
        (abs(a[:, :, 2] - cr) <= variation)
        & (abs(a[:, :, 1] - cg) <= variation)
        & (abs(a[:, :, 0] - cb) <= variation)
    )


def mask_blobs(
    mask: np.ndarray,
    cell_px: int,
    min_cells: int = 1,
    fill: float = 0.25,
) -> list[tuple[int, int, int, int, int]]:
    """Connected cell groups of a boolean mask: (x1, y1, x2, y2, pixels) in mask pixels."""
    cs = max(1, int(cell_px))
    h, w = (mask.shape[0] // cs) * cs, (mask.shape[1] // cs) * cs
    if h == 0 or w == 0:
        return []
    m = mask[:h, :w]
    counts = m.reshape(h // cs, cs, w // cs, cs).sum(axis=(1, 3))
    grid = counts >= max(1, fill * cs * cs)
    seen = np.zeros_like(grid)
    out = []
    gh, gw = grid.shape
    for gy in range(gh):
        for gx in range(gw):
            if not grid[gy, gx] or seen[gy, gx]:
                continue
            stack = [(gy, gx)]
            cells = []
            while stack:
                y, x = stack.pop()
                if y < 0 or x < 0 or y >= gh or x >= gw or seen[y, x] or not grid[y, x]:
                    continue
                seen[y, x] = True
                cells.append((y, x))
                stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
            if len(cells) < min_cells:
                continue
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            x1, x2 = min(xs) * cs, (max(xs) + 1) * cs
            y1, y2 = min(ys) * cs, (max(ys) + 1) * cs
            out.append((x1, y1, x2, y2, int(m[y1:y2, x1:x2].sum())))
    return sorted(out)


def find_blobs(
    g,
    rect: tuple[int, int, int, int],
    color: int | None = None,
    variation: int = 0,
    *,
    mask_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    anchor: Anchor | None = None,
    min_w: int = 0,
    min_h: int = 0,
    cell: int = 6,
    fill: float = 0.25,
) -> list[Blob]:
    """Blobs of `color` (or of `mask_fn(img)`) inside a logical rect (x1, y1, x2, y2),
    as logical boxes. `cell` is the grid cell in logical px; blobs narrower than `min_w`
    or lower than `min_h` (logical) are dropped. The rect and the results share `anchor`."""
    vp = g._viewport()
    sx1, sy1 = vp.to_screen(rect[0], rect[1], anchor)
    sx2, sy2 = vp.to_screen(rect[2], rect[3], anchor)
    # clipped to the client: a centre-anchored rect measured on the wider reference client
    # starts left of a 16:9 client's edge
    c = vp.client
    sx1, sy1 = max(sx1, c.x), max(sy1, c.y)
    sx2, sy2 = min(sx2, c.x + c.w), min(sy2, c.y + c.h)
    if sx2 <= sx1 or sy2 <= sy1:
        return []
    img = capture.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1))[:, :, :3]
    mask = mask_fn(img) if mask_fn is not None else colour_mask(img, color or 0, variation)
    px_per_logical = img.shape[1] / max(1, rect[2] - rect[0])
    cs = max(2, round(cell * px_per_logical))
    out = []
    for x1, y1, x2, y2, n in mask_blobs(mask, cs, fill=fill):
        lx1, ly1 = vp.to_logical(sx1 + x1, sy1 + y1, anchor)
        lx2, ly2 = vp.to_logical(sx1 + x2, sy1 + y2, anchor)
        b = Blob(lx1, ly1, lx2, ly2, n)
        if b.w >= min_w and b.h >= min_h:
            out.append(b)
    return out
