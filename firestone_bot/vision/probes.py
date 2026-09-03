"""PixelSearch equivalent on numpy BGRA images.

AHK `PixelSearch ... Fast RGB` with variation V matches a pixel when each of R, G, B is within
±V of the target, and returns the FIRST hit scanning left-to-right, top-to-bottom.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.platform.window import Rect


def color_rgb(color: int) -> tuple[int, int, int]:
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


def match_mask(img: np.ndarray, color: int, variation: int) -> np.ndarray:
    """Boolean (H, W) mask of pixels matching `color` within `variation` per channel."""
    r, g, b = color_rgb(color)
    px = img[:, :, :3].astype(np.int16)  # BGRA -> B, G, R
    return (
        (np.abs(px[:, :, 2] - r) <= variation)
        & (np.abs(px[:, :, 1] - g) <= variation)
        & (np.abs(px[:, :, 0] - b) <= variation)
    )


def pixel_search_image(img: np.ndarray, color: int, variation: int) -> tuple[int, int] | None:
    """First matching pixel (x, y) in row-major order inside `img`, or None."""
    m = match_mask(img, color, variation)
    hits = np.argwhere(m)
    if hits.size == 0:
        return None
    y, x = hits[0]
    return int(x), int(y)


def pixel_search_in(
    img: np.ndarray, img_origin: Rect, rect: Rect, color: int, variation: int
) -> tuple[int, int] | None:
    """Search `rect` (screen coords) inside `img` captured at `img_origin`. Returns screen (x, y)."""
    x0 = rect.x - img_origin.x
    y0 = rect.y - img_origin.y
    x1 = min(x0 + rect.w, img.shape[1])
    y1 = min(y0 + rect.h, img.shape[0])
    x0, y0 = max(0, x0), max(0, y0)
    if x1 <= x0 or y1 <= y0:
        return None
    hit = pixel_search_image(img[y0:y1, x0:x1], color, variation)
    if hit is None:
        return None
    return hit[0] + x0 + img_origin.x, hit[1] + y0 + img_origin.y


def pixel_at(img: np.ndarray, x: int, y: int) -> int:
    """0xRRGGBB at image pixel (x, y)."""
    b, g, r = (int(v) for v in img[y, x, :3])
    return (r << 16) | (g << 8) | b
