"""Red notification bells / badges read as a count of red pixels in a rect.

The AHK bot probed one exact colour (0xF41000, variation 1 to 32); the bells shade from
0xFA0503 to 0xE73B38 and the Blessings bell is 0xF40000 on the owner's Windows client
(2026-09-08), so exact colours missed. A bell is a 30 px red disc with a white bell: hundreds
of red pixels, where an outline or a red gem gives a handful.
"""

from __future__ import annotations

MIN_PIXELS = 25


def red_pixels(g, rect: tuple[int, int, int, int]) -> int:
    img = g.region_image(rect).astype(int)
    b, gr, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    return int(((r > 190) & (gr < 90) & (b < 90)).sum())


def has_bell(g, rect: tuple[int, int, int, int], min_pixels: int = MIN_PIXELS) -> bool:
    return red_pixels(g, rect) >= min_pixels
