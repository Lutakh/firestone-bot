"""Screen capture on macOS through Quartz, colour-matched to sRGB.

Why not mss here: CGWindowListCreateImage returns pixels in the DISPLAY colour space (Display
P3 on recent Macs), so the atlas colours (sRGB, measured on Windows) are off by 10-40 units
on saturated sprites (measured 2026-09-05: the blue mode button 0x1089FF read 0x3C84F7).
Drawing the CGImage into a bitmap context whose colour space is sRGB makes Quartz do the
conversion natively (0x0B86FF after conversion, inside the atlas tolerance).

Requests are in points (Quartz), results in physical pixels (2x on Retina), BGRA like mss.
"""

from __future__ import annotations

import numpy as np


def _image_to_bgra(image) -> np.ndarray:
    """Draw a CGImage into an sRGB BGRA bitmap and return it as an (H, W, 4) array."""
    import Quartz

    w, h = Quartz.CGImageGetWidth(image), Quartz.CGImageGetHeight(image)
    cs = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    ctx = Quartz.CGBitmapContextCreate(
        None,
        w,
        h,
        8,
        w * 4,
        cs,
        Quartz.kCGImageAlphaPremultipliedFirst | Quartz.kCGBitmapByteOrder32Little,  # BGRA
    )
    Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, w, h), image)
    srgb = Quartz.CGBitmapContextCreateImage(ctx)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(srgb))
    bpr = Quartz.CGImageGetBytesPerRow(srgb)
    buf = np.frombuffer(bytes(data), dtype=np.uint8)
    return buf.reshape(h, bpr // 4, 4)[:, :w]


def grab_screen_points(left: int, top: int, width: int, height: int) -> np.ndarray:
    """Capture a screen rect given in points (everything on screen), physical pixels out."""
    import Quartz

    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectMake(left, top, width, height),
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if image is None:
        raise RuntimeError("CGWindowListCreateImage failed (Screen Recording permission?)")
    return _image_to_bgra(image)


def grab_window(window_id: int) -> np.ndarray | None:
    """Capture ONE window whatever covers it (its full bounds, no shadow); None on failure."""
    import Quartz

    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming,
    )
    return None if image is None else _image_to_bgra(image)
