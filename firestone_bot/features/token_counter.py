"""Token counters of the spend screens read as numbers: a hit counts when the counter drops.

The chaos rift counted a hit when its green Hit button looked grey right after the click,
but the pointer was still on the button and a hovered button is drawn lighter, so the probe
missed at once and every click counted (10 counted with one free moonstone left, users on
Steam and Epic, 2026-09-24). The arcane crystal counted any redraw of its counter area,
which also holds sky and the box edge (15 counted, 14 made). The counters themselves say
what the game took: the free moonstone counter drops as soon as a hit starts, the pickaxe
counter as soon as the crystal is hit.
"""

from __future__ import annotations

import logging

import numpy as np

from firestone_bot.game import Game
from firestone_bot.vision import atlas, digits

log = logging.getLogger("firestone_bot")

POLL_MS = 150
EDGE_COLS = 2  # bright pixels in the outer columns: a digit cut by the rect


def read_image(g: Game, img: np.ndarray) -> int | None:
    """The number in a counter crop; None when a digit touches the left or right edge (a rect
    misplaced on another window shape cut "10" into "0" in a test: never a wrong number)."""
    if img.size == 0:
        return None
    cols = digits.bright_mask(img).any(axis=0)
    if cols[:EDGE_COLS].any() or cols[-EDGE_COLS:].any():
        return None
    return g.digit_reader().read(img)


def read(g: Game, rect: tuple[int, int, int, int]) -> int | None:
    try:
        return read_image(g, g.region_image(rect, atlas.ANCHOR_TOP_RIGHT))
    except Exception:  # a capture error, missing digit templates: the caller falls back
        log.debug("token counter %s unreadable", rect, exc_info=True)
        return None


def read_stable(g: Game, rect: tuple[int, int, int, int]) -> int | None:
    """The counter when two reads a moment apart agree, else None (a redraw in progress)."""
    first = read(g, rect)
    if first is None:
        return None
    g.sleep(POLL_MS)
    return first if read(g, rect) == first else None


def wait_drop(
    g: Game, rect: tuple[int, int, int, int], before: int, timeout_ms: float
) -> int | None:
    """The counter once it reads the same value below `before` twice in a row, None when it
    did not drop within `timeout_ms` (the click was not taken)."""
    last = None
    waited = 0.0
    while waited < timeout_ms:
        g.sleep(POLL_MS)
        waited += POLL_MS
        now = read(g, rect)
        if now is not None and now < before:
            if now == last:
                return now
            last = now
        else:
            last = None
    return None
