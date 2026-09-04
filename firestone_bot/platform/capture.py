"""Screen capture via mss. grab() returns a numpy array in BGRA order, shape (H, W, 4).

One mss instance per thread: on Windows mss stores its GDI handles in a threading.local that
is only initialised by the creating thread, so a shared instance raises AttributeError when
another thread (bot worker vs. GUI self-test) grabs with it.
"""

from __future__ import annotations

import threading

import numpy as np

from .window import Rect

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


def grab(rect: Rect) -> np.ndarray:
    shot = _sct().grab({"left": rect.x, "top": rect.y, "width": rect.w, "height": rect.h})
    return np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)


def save_png(img: np.ndarray, path: str) -> None:
    import mss.tools

    h, w = img.shape[:2]
    rgb = np.ascontiguousarray(img[:, :, 2::-1])  # BGRA -> RGB (to_png wants 3 bytes/pixel)
    mss.tools.to_png(rgb.tobytes(), (w, h), output=path)
