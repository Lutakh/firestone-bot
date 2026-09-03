"""Screen capture via mss. grab() returns a numpy array in BGRA order, shape (H, W, 4)."""

from __future__ import annotations

import numpy as np

from .window import Rect

_SCT = None


def _sct():
    global _SCT
    if _SCT is None:
        import mss

        _SCT = mss.mss()
    return _SCT


def grab(rect: Rect) -> np.ndarray:
    shot = _sct().grab({"left": rect.x, "top": rect.y, "width": rect.w, "height": rect.h})
    return np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)


def save_png(img: np.ndarray, path: str) -> None:
    import mss.tools

    h, w = img.shape[:2]
    rgb = np.ascontiguousarray(img[:, :, 2::-1])  # BGRA -> RGB (to_png wants 3 bytes/pixel)
    mss.tools.to_png(rgb.tobytes(), (w, h), output=path)
