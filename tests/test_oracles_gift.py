"""Oracle's gifts and mystery boxes: the open button is located in its row, wherever the row
sits (the latest game version draws it ~50 px lower; Qualitas, Steam, 2026-10-22)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from firestone_bot.features import oracles_gift
from firestone_bot.vision import atlas

# Qualitas's video (854x480 of a 1920x1080 screen, client 1920x1009 at y 23): the gift dialog's
# button row, GIFT_BUTTON_ROW, with its single x1 button at logical 850..1068 x 912..982; BGR
NEW_ROW = np.load(Path(__file__).parent / "fixtures" / "gift-button-row-new.npy")
GREEN = (0x08, 0xA0, 0x0A)  # GREEN_BUTTON 0x0AA008, BGR


def _row(*buttons):
    """GIFT_BUTTON_ROW at one logical px a pixel, with green buttons (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = atlas.GIFT_BUTTON_ROW
    img = np.full((y2 - y1, x2 - x1, 3), (120, 70, 40), np.uint8)  # the dialog's blue
    for bx1, by1, bx2, by2 in buttons:
        img[by1 - y1 : by2 - y1, bx1 - x1 : bx2 - x1] = GREEN
    return img


class FakeGame:
    def __init__(self, row):
        self.row = row

    def wait_still(self, max_ms=1500):
        return True

    def region_image(self, rect, anchor=None):
        assert rect == atlas.GIFT_BUTTON_ROW
        assert anchor == atlas.ANCHOR_CENTER  # the dialog is centred
        return self.row

    def found(self, probe):
        raise AssertionError("the AHK points are only a fallback")


def test_the_new_x1_button_is_clicked_in_its_middle():
    p = oracles_gift._open_button(FakeGame(NEW_ROW))
    assert 850 < p.x < 1068 and 912 < p.y < 982
    assert abs(p.y - 947) <= 12  # the middle of its height (the gift icon cuts its left part)
    assert p.anchor == atlas.ANCHOR_CENTER
    # the AHK point (914, 898) was above the button: the box stayed unopened
    assert atlas.GIFT_OPEN_BUTTONS[2][1].y < 912


def test_the_old_row_still_works():
    p = oracles_gift._open_button(FakeGame(_row((860, 866, 1055, 930))))
    assert (p.x, p.y) == (957, 898)


def test_the_largest_count_is_the_rightmost_button():
    row = _row((700, 912, 900, 982), (930, 912, 1130, 982))
    p = oracles_gift._open_button(FakeGame(row))
    assert 930 < p.x < 1130


def test_without_a_green_button_the_ahk_points_decide():
    g = FakeGame(_row())
    seen = []
    g.found = lambda probe: seen.append(probe.name) or probe is atlas.GIFT_OPEN_BUTTONS[2][0]
    p = oracles_gift._open_button(g)
    assert p == atlas.GIFT_OPEN_BUTTONS[2][1] and len(seen) == 3
