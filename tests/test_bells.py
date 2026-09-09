"""Bells read as red-pixel counts; the main-screen bells scale their threshold."""

import numpy as np

from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas, bells
from firestone_bot.vision.viewport import Viewport


class _G:
    def __init__(self, img, client=None):
        self.img = img
        self.vp = Viewport(client or Rect(0, 31, 1920, 1009))
        self.anchors = []

    def _viewport(self):
        return self.vp

    def region_image(self, rect, anchor=None):
        self.anchors.append(anchor)
        return self.img


def _disc(radius):
    img = np.zeros((40, 40, 3), np.uint8)
    yy, xx = np.ogrid[:40, :40]
    img[(yy - 20) ** 2 + (xx - 20) ** 2 <= radius**2] = (0, 0x10, 0xF4)  # BGR red
    return img


def test_bell_in_needs_more_than_a_stray_edge():
    g = _G(_disc(3))  # ~28 red pixels: the edge of a red icon
    assert not bells.bell_in(g, atlas.EVENTS_BELL)
    g = _G(_disc(15))  # a bell: ~700 red pixels
    assert bells.bell_in(g, atlas.EVENTS_BELL)
    assert g.anchors == [atlas.ANCHOR_BOTTOM_CENTER]  # the probe's anchor is used


def test_scaled_threshold_follows_the_client_scale():
    g = _G(_disc(15), Rect(0, 0, 3840, 2160))  # 4K: rel scale 2.14, pixels x4.6
    assert bells.scaled(g, 100) > 400
    g = _G(_disc(15), Rect(0, 0, 1280, 720))
    assert bells.scaled(g, 100) < 60
