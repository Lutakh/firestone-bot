"""Cycle statistics (stats.py) and the green-button finder (vision/buttons.py)."""

import re

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
        (86_400_000, "1 day"),  # a second unit at zero is left out
        (90_000_000, "1 day 1 hour"),
        (97_200_000, "1 day 3 hours"),
        (555_555_000, "6 days 10 hours"),
        (604_799_999, "6 days 23 hours"),  # rounded down: 6 d 23 h 59 min
        (604_800_000, "1 week"),
        (691_200_000, "1 week 1 day"),
        (1_209_600_000, "2 weeks"),
        (1_567_397_896, "2 weeks 4 days"),  # the owner's total on 2026-09-28: "2w4d", "435h23m"
        (2_591_999_999, "4 weeks 1 day"),
        (2_627_999_999, "4 weeks 2 days"),
        (2_628_000_000, "1 month"),
        (2_714_400_000, "1 month 1 day"),
        (10_000_000_000, "3 months 24 days"),
        (28_900_000_000, "10 months 30 days"),
        (31_535_999_999, "11 months 30 days"),  # a month is 30 d 10 h, so '12 months' never shows
        (31_536_000_000, "1 year"),
        (34_164_000_000, "1 year 1 month"),
        (36_792_000_000, "1 year 2 months"),
        (91_980_000_000, "2 years 11 months"),
        (2_549_160_000_000, "80 years 10 months"),  # the widest string below 100 years (Camp)
    ],
)
def test_fmt_ms_long_durations(ms, text):
    assert stats.fmt_ms(ms) == text
    assert stats.fmt_ms(str(ms)) == text  # settings.ini values are strings
    # Workshop joins the two worded units with "and"; one unit or a stopwatch form is unchanged
    worded = re.fullmatch(r"(\d+ [a-z]+) (\d+ [a-z]+)", text)
    anded = f"{worded[1]} and {worded[2]}" if worded else text
    assert stats.fmt_ms(ms, joiner=" and ") == anded


def test_fmt_ms_words_read_like_english():
    # the smaller unit after each worded unit and how many of it fit (a month holds 30 d 10 h)
    after = {"year": ("month", 12), "month": ("day", 31), "week": ("day", 7), "day": ("hour", 24)}
    words = re.compile(r"(\d+) (year|month|week|day)(s?)(?: (\d+) (month|day|hour)(s?))?")
    for day in range(1, 3 * 366):  # every day over 3 years: the millisecond before, on, 1 h after
        for ms in (day * 86_400_000 - 1, day * 86_400_000, day * 86_400_000 + 3_600_000):
            text = stats.fmt_ms(ms)
            if ms < 86_400_000:
                assert text == "23h59m"
                continue
            units = words.fullmatch(text)
            assert units, text
            for n, plural in ((units[1], units[3]), (units[4], units[6])):
                if n is not None:  # never "0 days", "1 days" or "2 day"
                    assert int(n) > 0 and (plural == "s") == (int(n) != 1), text
            small, fit = after[units[2]]
            assert units[4] is None or (units[5] == small and int(units[4]) < fit), text
            assert units[2] != "week" or int(units[1]) <= 4, text  # 5 weeks read as 1 month


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
