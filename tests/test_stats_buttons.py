"""Cycle statistics (stats.py) and the green-button finder (vision/buttons.py)."""

import numpy as np
import pytest

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
    assert stats.fmt_ms(-5) == "-"
    assert stats.fmt_ms("abc") == "-"
    assert stats.fmt_ms(None) == "-"
    assert stats.fmt_ms(" 45000.7 ") == "45s"


@pytest.mark.parametrize(
    "ms, text",
    [
        (999, "0s"),
        (86_399_999, "23h59m"),
        (86_400_000, "1d0h"),
        (555_555_000, "6d10h"),
        (604_799_999, "6d23h"),  # rounded down: 6 d 23 h 59 min
        (604_800_000, "1w0d"),
        (1_567_397_896, "2w4d"),  # the owner's total on 2026-09-28, "435h23m" before
        (2_591_999_999, "4w1d"),
        (2_627_999_999, "4w2d"),
        (2_628_000_000, "1mo0d"),
        (10_000_000_000, "3mo24d"),
        (28_900_000_000, "10mo30d"),  # the widest string in every skin (test_gui_camp)
        (31_500_000_000, "11mo30d"),
        (31_535_999_999, "11mo30d"),  # a month is 30 d 10 h, so '12mo' never shows
        (31_536_000_000, "1y0mo"),
        (91_980_000_000, "2y11mo"),
    ],
)
def test_fmt_ms_long_durations(ms, text):
    assert stats.fmt_ms(ms) == text
    assert stats.fmt_ms(str(ms)) == text  # settings.ini values are strings
    assert len(text) <= 7 and text.isascii() and " " not in text  # the Camp tile at 980x680


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
