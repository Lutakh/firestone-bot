"""Find the green buttons drawn inside a region, instead of clicking fixed points.

The game lays several screens out as a row of cards whose button is only there when the
action is available (chest dialog, liberation and dungeon missions): a fixed point misses
the button as soon as the row holds fewer cards or was scrolled (owner and Ixyon,
2026-09-09). A button is a solid green rectangle; nothing else on those screens is green,
so a projection of the green mask is enough to locate them.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Point
from firestone_bot.vision.probes import match_mask

MIN_W = 100  # logical px: a button is 190 to 250 wide
MIN_H = 25  # and about 55 high
FILL = 0.5  # share of the band that must be green


def green_boxes(
    g, rect: tuple[int, int, int, int], min_w: int = MIN_W, min_h: int = MIN_H, variation: int = 30
) -> list[tuple[int, int, int, int]]:
    """Logical (x1, y1, x2, y2) of every green button inside `rect`, left to right.

    Buttons side by side (one per card) are told apart by their columns; two buttons in the
    same columns but on different rows would be reported as one box.
    """
    x1, y1, x2, y2 = rect
    img = g.region_image(rect)
    mask = match_mask(img, atlas.GREEN_BUTTON, variation)
    h, w = mask.shape
    if not h or not w:
        return []
    fx, fy = (x2 - x1) / w, (y2 - y1) / h
    min_w_px, min_h_px = min_w / fx, min_h / fy
    cols = mask.sum(axis=0) >= min_h_px * FILL
    out: list[tuple[int, int, int, int]] = []
    start = None
    for i, on in enumerate(list(cols) + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= min_w_px:
                band = mask[:, start:i]
                rows = np.nonzero(band.sum(axis=1) >= (i - start) * FILL)[0]
                if len(rows) >= min_h_px:
                    out.append(
                        (
                            x1 + int(start * fx),
                            y1 + int(rows[0] * fy),
                            x1 + int(i * fx),
                            y1 + int((rows[-1] + 1) * fy),
                        )
                    )
            start = None
    return out


def green_buttons(g, rect: tuple[int, int, int, int], **kw) -> list[Point]:
    """Centres of the green buttons inside `rect`, left to right."""
    return [Point((b[0] + b[2]) // 2, (b[1] + b[3]) // 2) for b in green_boxes(g, rect, **kw)]
