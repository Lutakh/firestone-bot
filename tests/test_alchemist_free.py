"""The alchemist's free Speed up is told from the paid one by the gem icon, and the button,
not the brown timer pixel, decides whether a running experiment may be clicked."""

import numpy as np
import pytest

from firestone_bot.features import alchemist
from firestone_bot.features.alchemist import FREE, OTHER, PAID, button_look, free_to_complete
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas
from firestone_bot.vision.probes import color_rgb

GEM = (0x9D, 0x00, 0x9F)  # measured gem purple 0x9F009D (BGR)


def _button(orange: bool, gem=None, scale: float = 1.0):
    h, w = int(70 * scale), int(185 * scale)
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (200, 93, 102)  # BGR of the blue panel behind an idle slot
    if orange:
        r, g, b = color_rgb(atlas.ORANGE_1)
        img[int(10 * scale) : int(65 * scale), :] = (b, g, r)
    if gem is not None:
        s = int(22 * scale)
        y, x = int(30 * scale), int(50 * scale)
        img[y : y + s, x : x + s] = gem
    return img


class FakeGame:
    def __init__(self, reads, in_progress=False, collect=True):
        self.reads = list(reads)  # images returned by successive region_image calls
        self.in_progress = in_progress
        self.settings = Settings()
        self.settings.set("AlchCollect", "1" if collect else "0")
        self.vars = {}
        self.clicks = []
        self.pointer = None
        self.lines = []
        self.captures = []

    def region_image(self, rect):
        return self.reads.pop(0) if len(self.reads) > 1 else self.reads[0]

    def sleep(self, ms):
        pass

    def move_to(self, point):
        self.pointer = point

    def click(self):
        self.clicks.append(self.pointer)

    def found(self, probe):
        return self.in_progress if probe.name.endswith("_running") else False

    def toast(self, title, text, seconds):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)


SLOT = atlas.ALCHEMY_SLOTS[0]


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.2])
def test_looks_hold_at_every_client_size(scale):
    assert button_look(_button(True, GEM, scale)) == PAID
    assert button_look(_button(True, None, scale)) == FREE
    assert button_look(_button(False, None, scale)) == OTHER


def test_a_gem_shifted_by_a_colour_managed_capture_is_still_paid():
    """macOS captures shift colours by up to ~27 levels: the old mask read this gem as no
    gem at all, so a paid Speed up passed for free."""
    shifted = (147, 15, 165)  # BGR: r 165, g 15, b 147
    assert button_look(_button(True, shifted)) == PAID


def test_paid_speed_up_is_never_free():
    assert free_to_complete(FakeGame([_button(True, GEM)]), SLOT) is False


def test_free_speed_up_and_idle_slot():
    assert free_to_complete(FakeGame([_button(True)]), SLOT) is True
    assert free_to_complete(FakeGame([_button(False)]), SLOT) is False


def test_a_gem_drawn_on_the_second_read_blocks_the_click():
    assert free_to_complete(FakeGame([_button(True), _button(True, GEM)]), SLOT) is False


def test_paid_button_never_clicked_even_when_the_brown_pixel_misses():
    """2026-09-13: the brown timer pixel missed on a running experiment and the start click
    landed on its paid Speed up."""
    g = FakeGame([_button(True, GEM)], in_progress=False)
    alchemist._start(g, SLOT, collect=True)
    assert g.clicks == []
    assert "costs gems" in g.lines[-1]


def test_free_button_found_at_start_is_completed_and_not_started_again():
    g = FakeGame([_button(True)], in_progress=False)
    alchemist._start(g, SLOT, collect=True)
    assert g.clicks == [SLOT.collect]
    assert "free to complete" in g.lines[-1]


def test_collect_off_never_clicks_a_free_button():
    for brown in (True, False):
        g = FakeGame([_button(True)], in_progress=brown, collect=False)
        alchemist._start(g, SLOT, collect=False)
        assert g.clicks == []
        assert "left as is" in g.lines[-1]


def test_unrecognised_running_button_is_logged_once_and_never_clicked():
    g = FakeGame([_button(False)], in_progress=True)
    alchemist._start(g, SLOT, collect=True)
    alchemist._start(g, SLOT, collect=True)
    assert g.clicks == []
    assert g.captures == ["alchemy-running-dragon.png"]
    assert "button orange" in g.lines[-1]


def test_idle_slot_is_started():
    g = FakeGame([_button(False)], in_progress=False)
    alchemist._start(g, SLOT, collect=True)
    assert g.clicks == [SLOT.start]
