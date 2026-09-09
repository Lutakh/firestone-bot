"""Red notification bells / badges read as a count of red pixels in a rect.

The AHK bot probed one exact colour (0xF41000, variation 1 to 32); the bells shade from
0xFA0503 to 0xE73B38 and the Blessings bell is 0xF40000 on the owner's Windows client
(2026-09-08), so exact colours missed. A bell is a 30 px red disc with a white bell: hundreds
of red pixels, where an outline or a red gem gives a handful.
"""

from __future__ import annotations

MIN_PIXELS = 25
# A bell that only half enters its rect still leaves ~300 red pixels at the reference scale;
# the stray edge of a red icon next to it (the Events gift) leaves a few dozen.
BELL_PIXELS = 100


def red_pixels(g, rect: tuple[int, int, int, int], anchor=None) -> int:
    img = g.region_image(rect, anchor).astype(int)
    b, gr, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    return int(((r > 190) & (gr < 90) & (b < 90)).sum())


def has_bell(g, rect: tuple[int, int, int, int], min_pixels: int = MIN_PIXELS, anchor=None) -> bool:
    return red_pixels(g, rect, anchor) >= min_pixels


def scaled(g, pixels: int) -> int:
    """A pixel count measured at the reference scale, for the live client."""
    return int(pixels * g._viewport().rel_scale ** 2)


def bell_in(g, probe) -> bool:
    """A bell inside a probe's rect, by red-pixel count rather than by one matching pixel
    (a single pixel of a red icon next to the bell passed for it, 2026-09-09)."""
    rect = (probe.x1, probe.y1, probe.x2, probe.y2)
    return has_bell(g, rect, scaled(g, BELL_PIXELS), probe.anchor)
