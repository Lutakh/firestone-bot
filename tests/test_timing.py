"""Fast click timing: thumbnail change detection and the safe/fast behaviour of tap()."""

import numpy as np

from firestone_bot import game as game_mod
from firestone_bot.game import Game
from firestone_bot.platform.window import Rect, WindowInfo
from firestone_bot.settings import Settings
from firestone_bot.vision.viewport import Viewport


class _FakeCapture:
    def __init__(self):
        self.frame = np.zeros((270, 480, 4), dtype=np.uint8)
        self.grabs = 0

    def grab(self, rect):
        self.grabs += 1
        return self.frame


def _game(monkeypatch, timing="fast"):
    s = Settings()
    s.set("Timing", timing)
    g = Game(s, time_scale=0.01)
    g.window = WindowInfo(
        handle=1,
        pid=1,
        outer=Rect(0, 0, 480, 270),
        client=Rect(0, 0, 480, 270),
        title="Firestone",
        exe="Firestone",
        maximized=False,
        fullscreen=False,
    )
    g.vp = Viewport(g.window.client)
    fake = _FakeCapture()
    monkeypatch.setattr(game_mod, "capture", fake)
    monkeypatch.setattr(
        game_mod,
        "inp",
        type("I", (), {"move": staticmethod(lambda *a: None), "click": staticmethod(lambda: None)}),
    )
    return g, fake


def test_thumbnail_keeps_channels(monkeypatch):
    g, _fake = _game(monkeypatch)
    t = g._thumbnail()
    assert t.shape == (27, 48, 3)


def test_wait_change_returns_when_the_screen_changes(monkeypatch):
    g, fake = _game(monkeypatch)
    before = g._thumbnail()
    fake.frame[:, :, :3] = 200  # a dialog covering the whole screen
    assert g.wait_change(1500, before) is True
    assert g.stats["wait_saved_ms"] > 0


def test_wait_change_times_out_when_nothing_changes(monkeypatch):
    g, _fake = _game(monkeypatch)
    assert g.wait_change(300) is False


def test_safe_timing_never_captures(monkeypatch):
    g, fake = _game(monkeypatch, "safe")
    from firestone_bot.vision.atlas import Point

    g.tap(Point(10, 10), 500)
    assert fake.grabs == 0
    assert not g.fast()


def test_poll_interval_follows_the_timing_mode(monkeypatch):
    g, _ = _game(monkeypatch, "fast")
    assert g.poll_ms() == Game.POLL_FAST_MS
    g, _ = _game(monkeypatch, "safe")
    assert g.poll_ms() == Game.POLL_SAFE_MS


def test_wait_region_change_polls_faster_in_fast_timing(monkeypatch):
    g, fake = _game(monkeypatch, "fast")
    before = g.region_image((0, 31, 100, 60))
    assert g.wait_region_change((0, 31, 100, 60), before, timeout_ms=1000) is False
    assert fake.grabs >= 4  # 250 ms polls: four captures in one second, one in safe timing
