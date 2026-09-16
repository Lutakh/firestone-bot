"""The spend multiplier and mode labels of the token screens (fixtures: real crops of the
bottom-right buttons on a 1920x1009 client, BGR uint8)."""

import os

import numpy as np

from firestone_bot.features import multiplier
from firestone_bot.vision import atlas
from firestone_bot.vision.digits import DigitReader

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class _Viewport:
    rel_scale = 1.0


class FakeGame:
    """Serves one crop per label rect; records clicks."""

    def __init__(self, multiplier_label: str, mode_label: str):
        self.images = {
            atlas.SPEND_MULTIPLIER_LABEL: np.load(os.path.join(FIXTURES, multiplier_label)),
            atlas.SPEND_MODE_LABEL: np.load(os.path.join(FIXTURES, mode_label)),
        }
        self.log = []
        self._reader = DigitReader()

    def region_image(self, rect, anchor=None):
        return self.images[rect]

    def _viewport(self):
        return _Viewport()

    def digit_reader(self):
        return self._reader

    def status(self, msg):
        self.log.append(msg)

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def save_diagnostic(self, name):
        self.log.append(("diag", name))

    def tap(self, p, settle=0):
        self.log.append(("tap", p))


def test_multiplier_label_reads_x1_and_x5():
    assert multiplier.read_multiplier(FakeGame("spend-x1.npy", "spend-manual.npy")) == 1
    assert multiplier.read_multiplier(FakeGame("spend-x5.npy", "spend-manual.npy")) == 5


def test_mode_label_tells_manual_from_auto():
    assert multiplier.mode_is_manual(FakeGame("spend-x1.npy", "spend-manual.npy")) is True
    assert multiplier.mode_is_manual(FakeGame("spend-x1.npy", "spend-auto.npy")) is False


def test_x1_and_manual_pass_without_a_click():
    g = FakeGame("spend-x1.npy", "spend-manual.npy")
    assert multiplier.ensure_single(g, "Scarab") is True
    assert not [e for e in g.log if isinstance(e, tuple) and e[0] == "tap"]


def test_a_multiplier_that_never_comes_back_spends_nothing():
    g = FakeGame("spend-x5.npy", "spend-manual.npy")  # the click changes nothing here
    assert multiplier.ensure_single(g, "Scarab") is False
    taps = [e for e in g.log if isinstance(e, tuple) and e[0] == "tap"]
    assert len(taps) == multiplier.MAX_STEPS
    assert any("nothing spent" in m for m in g.log if isinstance(m, str))


def test_no_label_means_a_screen_without_the_pair():
    g = FakeGame("spend-x1.npy", "spend-manual.npy")
    g.images[atlas.SPEND_MULTIPLIER_LABEL] = np.zeros((70, 255, 3), dtype=np.uint8)
    assert multiplier.read_multiplier(g) is None
    assert multiplier.ensure_single(g, "Tavern") is True
