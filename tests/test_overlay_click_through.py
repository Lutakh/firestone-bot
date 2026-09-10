"""Overlay on macOS: Tk clears ignoresMouseEvents every time it maps the window, so the flag
is re-applied after each show and `click_through` follows what the window reports
(the Events click landed on the panel and raised the bot, 2026-09-10)."""

import pytest

from firestone_bot.gui import overlay


class FakeTop:
    def update_idletasks(self):
        pass


@pytest.fixture
def ov(monkeypatch):
    monkeypatch.setattr(overlay.sys, "platform", "darwin")
    o = overlay.GameOverlay.__new__(overlay.GameOverlay)
    o.top = FakeTop()
    o.capture_safe = True
    o.click_through = True
    return o


def test_click_through_follows_the_window_flag(ov, monkeypatch):
    monkeypatch.setattr(overlay, "_macos_click_through", lambda top: True)
    ov._reassert_click_through()
    assert ov.click_through is True


def test_a_flag_that_does_not_stick_makes_the_app_hide_the_panel(ov, monkeypatch):
    monkeypatch.setattr(overlay, "_macos_click_through", lambda top: False)
    ov._reassert_click_through()
    assert ov.click_through is False  # app._overlay_avoid then hides it before the click


def test_an_appkit_error_is_not_taken_for_click_through(ov, monkeypatch):
    def boom(top):
        raise RuntimeError("no AppKit")

    monkeypatch.setattr(overlay, "_macos_click_through", boom)
    ov._reassert_click_through()
    assert ov.click_through is False
