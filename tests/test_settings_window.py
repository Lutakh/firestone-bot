"""Settings window: recognised by its button row, closed by its own X, and a town building is
never clicked when the town did not come back (the tavern's point is "Patch notes" in the
settings window: that click opened the patch notes in the browser, 2026-09-10)."""

import pytest

from firestone_bot import game as game_mod
from firestone_bot.features import big_close as big_close_mod
from firestone_bot.features import main_menu as mm
from firestone_bot.features import open_town as open_town_mod
from firestone_bot.vision import atlas, blobs


class FakeGame:
    def __init__(self, settings_buttons=0, old_probe=False):
        self.settings_buttons = settings_buttons
        self.old_probe = old_probe
        self.taps = []
        self.statuses = []

    def found(self, probe):
        if probe is atlas.MM_SETTINGS_OPEN:
            return self.old_probe
        return False

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append(p)
        if p is atlas.SETTINGS_CLOSE:
            self.settings_buttons, self.old_probe = 0, False

    def fast(self):
        return True

    def focus(self):
        pass

    def status(self, s):
        self.statuses.append(s)

    def save_diagnostic(self, name):
        pass


@pytest.fixture(autouse=True)
def fake_blobs(monkeypatch):
    def find_blobs(g, rect, color=None, variation=0, **kw):
        return [
            blobs.Blob(200 + i * 320, 930, 420 + i * 320, 990, 9000)
            for i in range(g.settings_buttons)
        ]

    monkeypatch.setattr(mm.blobs, "find_blobs", find_blobs)


def test_the_button_row_tells_the_settings_window():
    assert mm.settings_open(FakeGame(settings_buttons=5))
    assert mm.settings_open(FakeGame(settings_buttons=4))  # one hovered
    assert not mm.settings_open(FakeGame(settings_buttons=1))


def test_the_old_probe_still_counts():
    assert mm.settings_open(FakeGame(old_probe=True))


def test_settings_are_closed_by_their_own_x():
    g = FakeGame(settings_buttons=5)
    mm.close_settings(g)
    assert g.taps == [atlas.SETTINGS_CLOSE]


def test_no_building_click_when_the_town_does_not_come_back(monkeypatch):
    monkeypatch.setattr(big_close_mod, "big_close", lambda g: None)
    monkeypatch.setattr(mm, "main_menu", lambda g: True)
    monkeypatch.setattr(open_town_mod, "open_town", lambda g: False)
    g = FakeGame()
    ok = game_mod.Game.open_screen(g, atlas.TOWN_TAVERN, atlas.TAVERN_CLOSE_X, via_town=True)
    assert ok is False
    assert g.taps == [atlas.TOWN_TAVERN]  # the first try only, not the retry
    assert any("town is not open" in s for s in g.statuses)
