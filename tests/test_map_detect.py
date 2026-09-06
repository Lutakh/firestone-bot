"""Mission detection on the world map: outlined white duration labels."""

from __future__ import annotations

import numpy as np

from firestone_bot.features import map_detect


def _digit(img, x, y, w=12, h=22):
    """A white block with a 2 px dark outline, like one bold digit."""
    img[y - 2 : y + h + 2, x - 2 : x + w + 2] = (40, 40, 40)
    img[y : y + h, x : x + w] = (255, 255, 255)


def _label(img, x, y, digits=4):
    for i in range(digits):
        _digit(img, x + i * 16, y)


def test_labels_found_and_isolated_shapes_ignored():
    img = np.full((400, 600, 3), (60, 120, 200), np.uint8)
    _label(img, 100, 100)  # "27:36"-like row of four digits
    _label(img, 400, 300, digits=3)  # "4:57"-like
    _digit(img, 300, 200)  # a single outlined block: not a label
    img[20:40, 500:560] = (255, 255, 255)  # plain white without outline: ignored
    labels = map_detect.find_labels(img)
    assert len(labels) == 2
    (x0, y0, x1, y1), (a0, b0, _a1, _b1) = sorted(labels)
    assert (x0, y0) == (100, 100) and x1 == 100 + 3 * 16 + 12 and y1 == 122
    assert (a0, b0) == (400, 300)


def test_find_missions_maps_labels_to_logical_icon_centres():
    img = np.full((800, 1600, 3), (60, 120, 200), np.uint8)
    _label(img, 200, 400)

    class G:
        def region_image(self, rect):
            assert rect == map_detect.atlas.MAP_DETECT_AREA
            return img

    (x, y), *rest = map_detect.find_missions(G())
    assert not rest
    x1, y1, x2, y2 = map_detect.atlas.MAP_DETECT_AREA
    fx, fy = (x2 - x1) / 1600, (y2 - y1) / 800
    assert x == x1 + int((200 + 200 + 3 * 16 + 12) / 2 * fx)
    assert y == y1 + int(411 * fy) - map_detect.atlas.MAP_LABEL_TO_ICON
