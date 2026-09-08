"""Colour blobs: grid connectivity, logical boxes, clipping to the client."""

import numpy as np

from firestone_bot.platform.window import Rect
from firestone_bot.vision import blobs
from firestone_bot.vision.viewport import Viewport


def test_mask_blobs_groups_cells_and_counts_pixels():
    m = np.zeros((40, 60), bool)
    m[4:16, 4:24] = True  # one box
    m[24:36, 40:56] = True  # another
    out = blobs.mask_blobs(m, 4)
    assert len(out) == 2
    (x1, y1, x2, y2, n) = out[0]
    assert (x1, y1, x2, y2) == (4, 4, 24, 16) and n == 12 * 20


def test_mask_blobs_ignores_sparse_cells():
    m = np.zeros((20, 20), bool)
    m[3, 3] = True  # one pixel: below the fill ratio
    assert blobs.mask_blobs(m, 4) == []


class _G:
    def __init__(self, client):
        self.vp = Viewport(client)

    def _viewport(self):
        return self.vp


def test_find_blobs_returns_logical_boxes(monkeypatch):
    # a client of the reference size: logical == client pixels (offset by the title bar)
    g = _G(Rect(0, 31, 1920, 1009))
    img = np.zeros((1009, 1920, 3), np.uint8)
    img[:, :] = (0x80, 0x40, 0x18)  # tree-like background (BGR of 0x184080)
    img[200:300, 500:900] = (0xDE, 0x49, 0x0D)  # a node box, client (500..900, 200..300)
    monkeypatch.setattr(
        blobs.capture, "grab", lambda r: img[r.y - 31 : r.y - 31 + r.h, r.x : r.x + r.w]
    )
    found = blobs.find_blobs(g, (0, 31, 1920, 1040), 0x1D49DE, 32, min_w=100, min_h=40)
    assert len(found) == 1
    b = found[0]
    assert abs(b.cx - 700) <= 6 and abs(b.cy - (250 + 31)) <= 6
    assert 390 <= b.w <= 412 and 94 <= b.h <= 112


def test_find_blobs_clips_a_rect_outside_the_client(monkeypatch):
    g = _G(Rect(0, 0, 1920, 1080))  # 16:9: centre-anchored logical 0 is left of the edge
    img = np.zeros((1080, 1920, 3), np.uint8)
    seen = {}

    def grab(r):
        seen["rect"] = r
        return img[r.y : r.y + r.h, r.x : r.x + r.w]

    monkeypatch.setattr(blobs.capture, "grab", grab)
    assert blobs.find_blobs(g, (0, 100, 800, 500), 0xFFFFFF, 0, anchor=(0.5, 0.5)) == []
    assert seen["rect"].x == 0 and seen["rect"].w > 0
