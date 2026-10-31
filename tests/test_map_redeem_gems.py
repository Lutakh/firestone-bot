"""Map missions: a button the bot believes free is never clicked when it shows a gem (three
users' missions completed with gems after a game update, 2026-10-22).

The mission popups (paid and free speed-ups, the Mission Rewards after them, the gem dialog
rule, the once-a-run captures) are read by their look: tests/test_map_popup_scenes.py runs
them on real crops at every client shape. Here: the map's Refresh Now and the paid reset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from firestone_bot.features import map_redeem
from firestone_bot.game import StepAborted
from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas, gems

# The owner's "Refresh Now" button (2026-10-22): orange, a gem and "120", BGR
PAID_REFRESH = np.load(Path(__file__).parent / "fixtures" / "map-refresh-paid.npy")
GEM = (0x9D, 0x00, 0x9F)  # the measured gem purple 0x9F009D, BGR
ORANGE = (0x10, 0x8C, 0xF5)


def _button(rect, gem: bool) -> np.ndarray:
    x1, y1, x2, y2 = rect
    img = np.zeros((y2 - y1, x2 - x1, 3), np.uint8)
    img[:, :] = ORANGE
    if gem:
        img[20:50, 30:60] = GEM
    return img


class FakeMap:
    """The map with its Refresh Now button; the mission check is the scene tests' business."""

    def __init__(self, free_reset=False, refresh=None):
        self.beats = []
        self.free_reset = free_reset
        self.refresh = refresh
        self.clicks = []
        self.pointer = None
        self.lines = []
        self.diagnostics = []
        self.vars = {}
        self.settings = self
        self.MapReset = "0"

    def get(self, key):
        return "0"

    def flag(self, key):
        return False

    def found(self, probe):
        return probe is atlas.MR_FREE_RESET and self.free_reset

    def region_image(self, rect, anchor=None):
        if rect == atlas.MR_REFRESH_RECT and self.refresh is not None:
            return self.refresh
        return _button(rect, False)

    def move_to(self, p):
        self.pointer = (p.x, p.y)

    def click(self):
        self.clicks.append(self.pointer)

    def status(self, text):
        self.lines.append(text)

    def toast(self, title, text, seconds):
        self.lines.append(f"{title}: {text}")

    def save_diagnostic(self, name):
        self.diagnostics.append(name)

    def heartbeat(self, msg, is_stop=False, important=False):
        self.beats.append((msg, important))

    def focus(self):
        pass

    def sleep(self, ms):
        pass

    def client_image(self):  # the map, nothing open on it (map_clear before the reset)
        return np.zeros((1009, 1920, 3), np.uint8), Rect(0, 0, 1920, 1009)


RESET = (atlas.MR_FREE_RESET_BUTTON.x, atlas.MR_FREE_RESET_BUTTON.y)


def _no_checks(monkeypatch):
    monkeypatch.setattr(map_redeem, "_checks", lambda g, watch=None: True)


def test_the_real_refresh_button_shows_its_gem():
    assert gems.gem_share(PAID_REFRESH) > 10 * gems.GEM_SHARE_MAX


def test_a_paid_refresh_is_never_clicked(monkeypatch):
    _no_checks(monkeypatch)
    g = FakeMap(free_reset=True, refresh=PAID_REFRESH)
    map_redeem.map_redeem(g)
    assert RESET not in g.clicks
    assert "Mission Restart: the refresh button costs gems, not clicked" in g.lines
    assert "mission-paid-refresh.png" in g.diagnostics


def test_a_free_refresh_is_still_clicked(monkeypatch):
    _no_checks(monkeypatch)
    g = FakeMap(free_reset=True, refresh=_button(atlas.MR_REFRESH_RECT, False))
    map_redeem.map_redeem(g)
    assert RESET in g.clicks


def test_free_refreshes_stop_with_free_speed_ups(monkeypatch):
    """A gem met after a speed-up believed free turns the bot's free refreshes off too."""
    _no_checks(monkeypatch)
    g = FakeMap(free_reset=True, refresh=_button(atlas.MR_REFRESH_RECT, False))
    g.vars[map_redeem.PAID_OFF] = 1
    map_redeem.map_redeem(g)
    assert RESET not in g.clicks


def test_a_paid_map_reset_happens_once_a_visit_whatever_the_safety_cap(monkeypatch, tmp_path):
    """MapReset (spend gems on resets, opt-in) looped without end with SafetyCap 0."""
    _no_checks(monkeypatch)
    g = FakeMap()
    g.map_state_path = str(tmp_path / "MapStartState.ini")
    g.MapReset = "1"
    resets = []
    g.found = lambda probe: probe is atlas.MR_RESET_AVAILABLE  # shown again after every reset
    g.move_to = lambda p: resets.append((p.x, p.y)) if p is atlas.MR_RESET_BUTTON else None
    map_redeem.map_redeem(g)
    assert len(resets) == 1
    assert "MapRedeem: one paid map reset this visit" in g.lines


def test_a_popup_left_open_ends_the_visit_before_the_troops(monkeypatch):
    """The mission check could not close a popup: no mission is started, no reset clicked."""
    monkeypatch.setattr(map_redeem, "_checks", lambda g, watch=None: False)
    started = []
    monkeypatch.setattr(map_redeem, "map_start", lambda g, watch=None: started.append(1) or True)
    g = FakeMap()
    g.found = lambda probe: probe is not atlas.MR_FREE_RESET  # idle troops, a reset shown
    g.MapReset = "1"
    with pytest.raises(StepAborted):  # the runner goes back to the main screen
        map_redeem.map_redeem(g)
    assert started == [] and g.clicks == []
