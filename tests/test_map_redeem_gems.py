"""Map missions: a button the bot believes free is never clicked when it shows a gem (three
users' missions completed with gems after a game update, 2026-10-22)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from firestone_bot.features import map_redeem
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
    """The mission panel with one mission in progress whose speed-up shows orange."""

    def __init__(self, early_gem=False, free_reset=False, refresh=None, dialog_gem=False):
        self.early_gem = early_gem
        self.dialog_gem = dialog_gem  # a gem shows in the dialog after the speed-up click
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
        if probe is atlas.MR_FREE_RESET:
            return self.free_reset
        return probe is atlas.MR_FREE_EARLY  # an orange speed-up, free or paid

    def region_image(self, rect, anchor=None):
        if rect == atlas.MR_REFRESH_RECT and self.refresh is not None:
            return self.refresh
        if rect == atlas.MR_EARLY_RECT:
            return _button(rect, self.early_gem)
        if rect == atlas.MR_GEM_DIALOG_RECT:
            return _button(rect, self.dialog_gem and EARLY in self.clicks)
        return _button(rect, False)

    def move_to(self, p):
        self.pointer = (p.x, p.y)

    def tap(self, p, settle_ms=1500, expect=None):
        self.pointer = (p.x, p.y)
        self.clicks.append(self.pointer)

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

    def wait_still(self, max_ms=1500):
        return True

    def focus(self):
        pass

    def sleep(self, ms):
        pass


EARLY = (atlas.MR_FREE_EARLY_BUTTON.x, atlas.MR_FREE_EARLY_BUTTON.y)
RESET = (atlas.MR_FREE_RESET_BUTTON.x, atlas.MR_FREE_RESET_BUTTON.y)


def test_the_real_refresh_button_shows_its_gem():
    assert gems.gem_share(PAID_REFRESH) > 10 * gems.GEM_SHARE_MAX


def test_a_paid_speed_up_is_never_clicked():
    g = FakeMap(early_gem=True)
    map_redeem._checks(g)
    assert EARLY not in g.clicks
    assert "Mission Check: the speed-up button costs gems, not clicked" in g.lines
    assert g.diagnostics == ["mission-paid-speed-up.png"]


def test_a_free_speed_up_is_still_clicked():
    g = FakeMap(early_gem=False)
    map_redeem._checks(g)
    assert EARLY in g.clicks
    assert not any("costs gems" in x for x in g.lines)


def test_a_paid_refresh_is_never_clicked():
    g = FakeMap(early_gem=True, free_reset=True, refresh=PAID_REFRESH)
    map_redeem.map_redeem(g)
    assert RESET not in g.clicks
    assert "Mission Restart: the refresh button costs gems, not clicked" in g.lines
    assert "mission-paid-refresh.png" in g.diagnostics


def test_a_free_refresh_is_still_clicked():
    g = FakeMap(early_gem=True, free_reset=True, refresh=_button(atlas.MR_REFRESH_RECT, False))
    map_redeem.map_redeem(g)
    assert RESET in g.clicks


def test_a_gem_dialog_after_a_speed_up_is_never_confirmed():
    """Second line of defence: a gem in the dialog that follows the click means the click was
    not free. OK is not tapped, free speed-ups and refreshes stop for the run, and an
    important heartbeat says so."""
    g = FakeMap(dialog_gem=True)
    map_redeem._checks(g)
    ok = (atlas.MR_DIALOG_OK.x, atlas.MR_DIALOG_OK.y)
    assert g.clicks.count(EARLY) == 1 and ok not in g.clicks
    assert not g.vars.get(map_redeem.PAID_OFF) and not g.beats  # once could be the map's purple
    assert "Mission Check: a gem showed after a speed-up click: not confirmed" in g.lines
    map_redeem._checks(g)  # the second time in a row: off for the run
    assert g.clicks.count(EARLY) == 2 and ok not in g.clicks
    assert g.vars[map_redeem.PAID_OFF] == 1
    beat = "Map missions: a gem showed after a speed-up click, nothing confirmed (see the log)"
    assert g.beats == [(beat, True)]
    assert "mission-gem-dialog.png" in g.diagnostics
    assert "mission-after-speed-up.png" in g.diagnostics  # the screen, once a run
    g.dialog_gem = False
    map_redeem._checks(g)  # the next visit of the run: no speed-up click at all
    assert g.clicks.count(EARLY) == 2


def test_a_paid_map_reset_happens_once_a_visit_whatever_the_safety_cap(tmp_path):
    """MapReset (spend gems on resets, opt-in) looped without end with SafetyCap 0."""
    g = FakeMap(early_gem=True)
    g.map_state_path = str(tmp_path / "MapStartState.ini")
    g.MapReset = "1"
    resets = []
    real_found = g.found

    def found(probe):
        if probe is atlas.MR_RESET_AVAILABLE:
            return True  # shown again after every reset
        return real_found(probe)

    g.found = found
    g.move_to = lambda p: resets.append((p.x, p.y)) if p is atlas.MR_RESET_BUTTON else None
    map_redeem.map_redeem(g)
    assert len(resets) == 1
    assert "MapRedeem: one paid map reset this visit" in g.lines
