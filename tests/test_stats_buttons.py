"""Cycle statistics (stats.py) and the green-button finder (vision/buttons.py)."""

import numpy as np

from firestone_bot import stats
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas, buttons
from firestone_bot.vision.probes import color_rgb


def test_note_cycle_accumulates_and_averages(tmp_path):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    assert stats.cycles_total(s) == 0 and stats.average_cycle_ms(s) == 0
    stats.note_cycle(s, 60_000)
    stats.note_cycle(s, 120_000)
    assert stats.cycles_total(s) == 2
    assert s.get("LastCycleMs") == "120000"
    assert stats.average_cycle_ms(s) == 90_000
    assert stats.cycles_total(Settings.load(str(tmp_path / "settings.ini"))) == 2


def test_fmt_ms():
    assert stats.fmt_ms(0) == "-"
    assert stats.fmt_ms("") == "-"
    assert stats.fmt_ms(45_000) == "45s"
    assert stats.fmt_ms(150_000) == "2m30s"
    assert stats.fmt_ms(11_100_000) == "3h05m"


class FakeGame:
    """Serves one image for any region: the buttons are drawn in logical coordinates."""

    def __init__(self, img, rect):
        self.img = img
        self.rect = rect

    def region_image(self, rect):
        assert rect == self.rect
        return self.img


def _canvas(rect, boxes):
    x1, y1, x2, y2 = rect
    img = np.zeros((y2 - y1, x2 - x1, 3), dtype=np.uint8)
    img[:, :] = (60, 40, 30)
    r, g, b = color_rgb(atlas.GREEN_BUTTON)
    for bx1, by1, bx2, by2 in boxes:
        img[by1 - y1 : by2 - y1, bx1 - x1 : bx2 - x1] = (b, g, r)  # BGR
    return img


def test_green_buttons_finds_each_button_left_to_right():
    rect = (100, 200, 1100, 400)
    boxes = [(150, 250, 350, 310), (600, 250, 800, 310)]
    g = FakeGame(_canvas(rect, boxes), rect)
    assert buttons.green_buttons(g, rect) == [
        atlas.Point(250, 280),
        atlas.Point(700, 280),
    ]


def test_green_buttons_ignores_small_marks_and_empty_screens():
    rect = (100, 200, 1100, 400)
    g = FakeGame(_canvas(rect, [(150, 250, 190, 270)]), rect)  # a small green tick
    assert buttons.green_buttons(g, rect) == []
    g = FakeGame(_canvas(rect, []), rect)
    assert buttons.green_buttons(g, rect) == []


def test_check_in_button_told_from_the_green_reward_tiles():
    from firestone_bot.features.shop import button_shaped
    from firestone_bot.vision.blobs import Blob

    button = Blob(1257, 880, 1431, 922, 5282)  # measured live, 1920x1009
    tile_frame = Blob(890, 539, 1030, 681, 2000)  # a claimed reward tile: square
    tick = Blob(900, 550, 990, 640, 1500)
    assert button_shaped([tile_frame, tick, button]) == [button]
    assert button_shaped([tile_frame, tick]) == []
