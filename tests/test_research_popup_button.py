"""The research popup's Research button is located, not read at a fixed point: game 9.1.3a
(Steam) draws the popup shorter and its button ~67 px lower, and every box was logged as
"shows no Research button" (report VNHYHL, 2026-10-22)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from firestone_bot.features import research
from firestone_bot.vision import atlas

FIXTURES = Path(__file__).parent / "fixtures"
# RS_POPUP_BUTTON_BAND at half a logical px per pixel, BGR: the player's 9.1.3a popup
# (client 1920x1017) and the owner's old-version popup (1920x1009)
NEW = np.load(FIXTURES / "research-popup-button-band-9.1.3a.npy")
OLD = np.load(FIXTURES / "research-popup-button-band-old.npy")


class FakePopup:
    """region_image of the band (and of any rect inside it) from a fixture."""

    def __init__(self, band_img):
        self.img = band_img
        self.lines = []

    def region_image(self, rect, anchor=None):
        assert anchor == atlas.ANCHOR_CENTER  # the popup is centred
        bx1, by1, bx2, by2 = atlas.RS_POPUP_BUTTON_BAND
        fy = self.img.shape[0] / (by2 - by1)
        fx = self.img.shape[1] / (bx2 - bx1)
        x1, y1, x2, y2 = rect
        return self.img[
            int((y1 - by1) * fy) : int((y2 - by1) * fy), int((x1 - bx1) * fx) : int((x2 - bx1) * fx)
        ]

    def sleep(self, ms):
        pass

    def status(self, text):
        self.lines.append(text)

    def found(self, probe):
        raise AssertionError("the fixed probe is only a fallback")


def test_the_9_1_3a_button_is_found_and_pressed_in_its_middle():
    p = research.popup_button(FakePopup(NEW))
    assert 654 < p.x < 946 and 723 < p.y < 816  # the button, measured on the capture
    assert abs(p.x - 800) <= 6 and abs(p.y - 770) <= 6
    assert p.anchor == atlas.ANCHOR_CENTER
    # the fixed point read the "Original time" row above it
    assert atlas.RS_POPUP_RESEARCH_BUTTON.y < 723


def test_the_old_version_button_still_found():
    p = research.popup_button(FakePopup(OLD))
    assert 654 < p.x < 946 and 656 < p.y < 748
    assert abs(p.x - 800) <= 6 and abs(p.y - 702) <= 6


def test_no_green_button_falls_back_to_the_fixed_probe():
    g = FakePopup(np.zeros_like(NEW))
    g.found = lambda probe: probe is atlas.RS_POPUP_RESEARCH
    assert research.popup_button(g) == atlas.RS_POPUP_RESEARCH_BUTTON
    g.found = lambda probe: False
    assert research.popup_button(g) is None


def test_a_green_button_with_a_gem_is_never_pressed():
    img = NEW.copy()
    img[65:75, 85:95] = (0x9D, 0x00, 0x9F)  # a gem purple in the middle of the green button, BGR
    g = FakePopup(img)
    assert research.popup_button(g) is None
    assert "Research: the popup's green button shows a gem, not pressed" in g.lines


def test_a_popup_left_open_after_the_press_is_closed_then_the_start_is_seen(monkeypatch):
    """The popup dims the slot panels: a start under it does not read. 9.1.3a was never
    seen after a press; the old game closes the popup itself."""
    state = {"popup": True, "closed": 0}

    def panels(g):
        return [("running" if not state["popup"] else "empty", None), ("empty", None)]

    def close_popup(g):
        state["popup"] = False
        state["closed"] += 1

    class G:
        def found(self, probe):
            if probe is atlas.DIALOG_CLOSE_X:
                return not state["popup"]  # dimmed while the popup is open
            return False

        def sleep(self, ms):
            pass

    monkeypatch.setattr(research, "panels", panels)
    monkeypatch.setattr(research, "_close_popup", close_popup)
    assert research._started(G(), 0)
    assert state["closed"] == 1


def _x_game(monkeypatch, band_img):
    """A half-size client (the band crops are at half a logical px a pixel) showing the
    crop at RS_POPUP_X_BAND; capture.grab and found() read it like the Game does."""
    from firestone_bot.platform.window import Rect
    from firestone_bot.vision import blobs
    from firestone_bot.vision.probes import match_mask
    from firestone_bot.vision.viewport import Viewport

    vp = Viewport(Rect(0, 0, 960, 505))
    screen = np.zeros((505, 960, 3), np.uint8)
    x, y = vp.to_screen(*atlas.RS_POPUP_X_BAND[:2], atlas.ANCHOR_CENTER)
    h, w = band_img.shape[:2]
    screen[y : y + h, x : x + w] = band_img

    def grab(r):
        return screen[r.y : r.y + r.h, r.x : r.x + r.w]

    class G:
        def _viewport(self):
            return vp

        def found(self, p):
            r = vp.probe_rect_screen(p)
            return bool(match_mask(grab(r), p.color, p.variation + vp.variation_boost()).any())

    monkeypatch.setattr(blobs.capture, "grab", grab)
    return G()


def test_the_close_button_is_located_on_both_versions(monkeypatch):
    for name, centre in (("9.1.3a", (1233, 288)), ("old", (1239, 217))):
        g = _x_game(monkeypatch, np.load(FIXTURES / f"research-popup-x-band-{name}.npy"))
        p = research.popup_close(g)
        assert p is not None and p is not atlas.RS_POPUP_CLOSE  # located, not the fallback
        assert abs(p.x - centre[0]) <= 6 and abs(p.y - centre[1]) <= 6, (name, p)
        assert p.anchor == atlas.ANCHOR_CENTER


def test_no_close_button_on_the_tree_without_a_popup(monkeypatch):
    g = _x_game(monkeypatch, np.load(FIXTURES / "research-popup-x-band-tree.npy"))
    assert research.popup_close(g) is None
