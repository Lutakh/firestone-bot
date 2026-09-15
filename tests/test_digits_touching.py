"""Two digits that touch on the guild banner are read as two digits (fixtures: real crops of
the GUILD_LEVEL_REGION on two clients, 1920x1009)."""

import os

import numpy as np
from PIL import Image

from firestone_bot.vision import digits

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _bgr(name: str) -> np.ndarray:
    return np.array(Image.open(os.path.join(FIXTURES, name)).convert("RGB"))[:, :, ::-1].copy()


def test_touching_73_on_a_full_green_bar_is_read():
    assert digits.DigitReader().read(_bgr("guild-banner-73.png"), last_word=True) == 73


def test_separate_digits_still_read():
    assert digits.DigitReader().read(_bgr("guild-banner-151.png"), last_word=True) == 151


def test_split_touching_leaves_digit_shaped_runs_alone():
    rows = np.zeros((20, 40), dtype=bool)
    rows[:, 5:14] = True  # a lone digit, 9 px wide for 20 high
    assert digits.split_touching(rows, 5, 14) == [(5, 14)]
    rows[:, 14:16] = False
    rows[:, 16:27] = True  # two digits joined by one bright column at 14..16? no: a thin neck
    rows[10, 14:16] = True
    parts = digits.split_touching(rows, 5, 27)
    assert len(parts) == 2 and parts[0][1] <= 16 and parts[1][0] >= 14
