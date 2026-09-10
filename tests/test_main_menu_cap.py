"""main_menu: the cap counts closes that change nothing (four layers to close from the scarab
market, SafetyCap 3), and the rate pop-up is only closed through an X actually seen."""

import pytest

from firestone_bot.features import main_menu as mm
from firestone_bot.vision import atlas, blobs


class FakeScreens:
    """`layers` dialogs above the main screen; each big close removes one (the screen
    changes). On the main screen the big close opens the settings window (the gear)."""

    def __init__(self, layers, stuck=False, rate_bar=False, rate_x=False, cap="3"):
        self.layers = layers
        self.stuck = stuck  # closes do nothing
        self.settings_up = False
        self.rate_bar, self.rate_x = rate_bar, rate_x
        self.taps = []
        self.statuses = []
        self.style = "classic"
        self.settings = type("S", (), {"get": staticmethod(lambda k: cap)})()
        self.frame = 0
        self.vars = {}

    # screen model
    def _thumbnail(self):
        return self.frame

    def changed_since(self, before):
        return before != self.frame

    def big_close(self):
        self.taps.append("big_close")
        if self.stuck:
            return
        self.frame += 1
        if self.layers:
            self.layers -= 1
        else:
            self.settings_up = True

    # Game API
    def found(self, probe):
        if probe is atlas.MM_RATE_POPUP:
            return self.rate_bar
        return False

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append(p)
        if p is atlas.SETTINGS_CLOSE:
            self.settings_up = False

    def focus(self):
        pass

    def sleep(self, ms):
        pass

    def status(self, s):
        self.statuses.append(s)

    def save_diagnostic(self, name):
        self.statuses.append(f"diag {name}")


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(mm, "big_close", lambda g: g.big_close())
    monkeypatch.setattr(mm, "close_chooser", lambda g: False)
    monkeypatch.setattr(mm, "settings_open", lambda g: g.settings_up)

    def find_blobs(g, area, color=None, variation=0, **kw):
        if not g.rate_x:
            return []
        if color == atlas.DIALOG_RING:
            return [blobs.Blob(1364, 274, 1431, 340, 3000)]
        return [blobs.Blob(1380, 290, 1416, 326, 900)]

    monkeypatch.setattr(mm.blobs, "find_blobs", find_blobs)


def test_four_layers_are_closed_with_a_cap_of_three():
    g = FakeScreens(layers=4)
    assert mm.main_menu(g) is True
    assert g.taps.count("big_close") == 5  # four layers, then the gear
    assert g.taps[-1] is atlas.SETTINGS_CLOSE


def test_closes_that_change_nothing_stop_at_the_cap():
    g = FakeScreens(layers=2, stuck=True)
    assert mm.main_menu(g) is False
    assert g.taps.count("big_close") == 3


def test_the_hard_limit_holds_even_with_progress():
    g = FakeScreens(layers=50)
    assert mm.main_menu(g) is False
    assert g.taps.count("big_close") == mm.MAX_CLOSES


def test_rate_popup_closed_through_the_x_it_shows():
    g = FakeScreens(layers=0, rate_bar=True, rate_x=True)
    g.rate_bar_once = True
    mm._close_rate_popup(g)
    assert len(g.taps) == 1
    p = g.taps[0]
    assert (p.x, p.y) == (1397, 307)


def test_rate_bar_without_an_x_saves_one_capture_per_cycle():
    g = FakeScreens(layers=0, rate_bar=True, rate_x=False)
    mm._close_rate_popup(g)
    mm._close_rate_popup(g)
    assert sum("rate-popup-no-x" in s for s in g.statuses) == 1


def test_rate_bar_without_an_x_clicks_nothing():
    g = FakeScreens(layers=0, rate_bar=True, rate_x=False)
    mm._close_rate_popup(g)
    assert g.taps == []
    assert any("rate-popup-no-x" in s for s in g.statuses)
