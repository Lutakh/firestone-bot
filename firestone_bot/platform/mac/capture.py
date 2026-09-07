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

_srgb = None


def _image_to_bgra(image) -> np.ndarray:
    """Draw a CGImage into an sRGB BGRA bitmap and return it as an (H, W, 4) array.

    The bitmap memory is a Python bytearray handed to CGBitmapContextCreate: a context that
    allocates its own pixels was never freed by PyObjC once drawn into (measured 2026-09-07:
    +8 MB per capture, 240 GB after a night of polling; with our own buffer the process
    stays flat at ~320 MB over 150 captures)."""
    import Quartz

    global _srgb
    if _srgb is None:
        _srgb = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    w, h = Quartz.CGImageGetWidth(image), Quartz.CGImageGetHeight(image)
    buf = bytearray(w * 4 * h)
    ctx = Quartz.CGBitmapContextCreate(
        buf,
        w,
        h,
        8,
        w * 4,
        _srgb,
        Quartz.kCGImageAlphaPremultipliedFirst | Quartz.kCGBitmapByteOrder32Little,  # BGRA
    )
    Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, w, h), image)
    del ctx  # the context references buf; drop it before the array takes the buffer
    # no .copy(): the array keeps the bytearray alive, and a copy doubled every capture
    # (31 MB at 4K, owner's Mac 2026-09-07)
    return np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)


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
