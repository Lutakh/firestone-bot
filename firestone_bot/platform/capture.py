"""Screen capture. grab() returns a numpy array in BGRA order, shape (H, W, 4).

Rects are physical pixels (platform/types.py). Windows / Linux use mss. macOS uses Quartz
directly (platform/mac/capture.py: sRGB colour matching, which mss does not do); Quartz takes
points and returns physical pixels (2x on Retina), so the request is snapped to whole points
and the result cropped back to the exact pixel rect requested (mac_points_request()).

One mss instance per thread: on Windows mss stores its GDI handles in a threading.local that
is only initialised by the creating thread, so a shared instance raises AttributeError when
another thread (bot worker vs. GUI self-test) grabs with it.
"""

from __future__ import annotations

import math
import sys
import threading

import numpy as np

from .window import Rect, pixels_per_point

_local = threading.local()


def _sct():
    sct = getattr(_local, "sct", None)
    if sct is None:
        import mss

        sct = _local.sct = mss.mss()
    return sct


def close() -> None:
    """Release this thread's mss instance (its DC and bitmap are GDI objects; a thread that
    grabbed and exits without closing leaks them for the life of the process)."""
    sct = getattr(_local, "sct", None)
    if sct is not None:
        _local.sct = None
        try:
            sct.close()
        except Exception:  # noqa: BLE001, S110 - best effort, nothing to do about it
            pass


def mac_points_request(rect: Rect, factor: float) -> tuple[dict, int, int]:
    """Points rect covering `rect` (pixels) and the pixel offset of `rect` inside the capture."""
    left = math.floor(rect.x / factor)
    top = math.floor(rect.y / factor)
    right = math.ceil((rect.x + rect.w) / factor)
    bottom = math.ceil((rect.y + rect.h) / factor)
    req = {"left": left, "top": top, "width": right - left, "height": bottom - top}
    return req, rect.x - round(left * factor), rect.y - round(top * factor)


def grab(rect: Rect) -> np.ndarray:
    if sys.platform != "darwin":
        shot = _sct().grab({"left": rect.x, "top": rect.y, "width": rect.w, "height": rect.h})
        return np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
    from .mac.capture import grab_screen_points

    factor = pixels_per_point()
    req, ox, oy = mac_points_request(rect, factor)
    img = grab_screen_points(req["left"], req["top"], req["width"], req["height"])
    if img.shape[1] != round(req["width"] * factor):  # a display scale we did not expect
        raise RuntimeError(
            f"capture returned {img.shape[1]}x{img.shape[0]} for {req} at factor {factor}"
        )
    return img[oy : oy + rect.h, ox : ox + rect.w]


def save_png(img: np.ndarray, path: str) -> None:
    import mss.tools

    h, w = img.shape[:2]
    rgb = np.ascontiguousarray(img[:, :, 2::-1])  # BGRA -> RGB (to_png wants 3 bytes/pixel)
    mss.tools.to_png(rgb.tobytes(), (w, h), output=path)
