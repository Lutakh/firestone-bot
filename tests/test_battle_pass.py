"""Battle pass claims: a Claim button lower under a labelled tile is clicked in its middle, and a
claim counts once its button is gone (Qualitas, 2026-10-09: the click went just above the
lowered button and was counted as a claim thirty times in a row)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from firestone_bot.features import battle_pass
from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas
from firestone_bot.vision.probes import color_rgb
from firestone_bot.vision.viewport import Viewport

REF_CLIENT = Rect(0, 31, 1920, 1009)  # the reference: screen px = logical px
# A Golden-row Claim button of the owner's client (captures/bp2.png, 2026-09-04), BGR,
# client x 918..1098, y 490..562: the button itself spans x 928..1087, and only its rows
# 503..539 match GREEN_BUTTON (a lighter top, a darker lip); the white "Claim" leaves
# about 10 green pixels in the columns of its letters.
REAL_BUTTON = np.load(Path(__file__).parent / "fixtures" / "bp-claim-button.npy")
BACKGROUND = (150, 90, 40)  # BGR, the page's blue
# measured on Qualitas's video (1920x1080, windowed), logical
NORMAL = (688, 530, 848, 577)  # Golden row, under a plain tile
LOWERED = (427, 552, 587, 599)  # Golden row, under a "100%" tile
FREE = (688, 934, 848, 984)
HEXAGON = (468, 655, 551, 694)  # a milestone of the track, green too


class FakePass:
    def __init__(self, buttons, track=(), real=()):
        self.real = [list(r) for r in real]  # [left, top, responds] of real buttons
        self.vp = Viewport(REF_CLIENT)
        # [x1, y1, x2, y2, responds]
        self.buttons = [list(b) + [True] if len(b) == 4 else list(b) for b in buttons]
        self.track = list(track)
        self.pointer = None
        self.clicks = []
        self.wheels = 0
        self.lines = []
        self.diagnostics = []

    def grab(self, rect):
        img = np.zeros((rect.h, rect.w, 3), np.uint8)
        img[:, :] = BACKGROUND
        r, g, b = color_rgb(atlas.GREEN_BUTTON)
        for x1, y1, x2, y2, *_ in self.buttons + [list(t) for t in self.track]:
            ax1, ay1 = max(x1 - rect.x, 0), max(y1 - rect.y, 0)
            ax2, ay2 = min(x2 - rect.x, rect.w), min(y2 - rect.y, rect.h)
            if ax1 < ax2 and ay1 < ay2:
                img[ay1:ay2, ax1:ax2] = (b, g, r)
                # the white "Claim" in the middle
                mx, my = (ax1 + ax2) // 2, (ay1 + ay2) // 2
                img[max(my - 8, ay1) : min(my + 8, ay2), max(mx - 30, ax1) : mx + 30] = 255
        h, w = REAL_BUTTON.shape[:2]
        for left, top, _ in self.real:
            x0, y0 = left - rect.x, top - rect.y
            if 0 <= x0 and x0 + w <= rect.w and 0 <= y0 and y0 + h <= rect.h:
                img[y0 : y0 + h, x0 : x0 + w] = REAL_BUTTON
        return img

    def move_to(self, p):
        self.pointer = (p.x, p.y)

    def move_screen(self, sx, sy):
        self.pointer = (sx, sy)

    def click(self):
        x, y = self.pointer
        self.clicks.append((x, y))
        for b in self.buttons:
            if b[0] <= x < b[2] and b[1] <= y < b[3] and b[4]:
                self.buttons.remove(b)
                return
        for r in self.real:  # the button drawn at client y 498..551 of the crop's 490
            if r[0] + 10 <= x < r[0] + 170 and r[1] + 8 <= y < r[1] + 61 and r[2]:
                self.real.remove(r)
                return

    def wheel(self, n):
        self.wheels += 1

    def sleep(self, ms):
        pass

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.diagnostics.append(name)


@pytest.fixture
def make(monkeypatch):
    def build(buttons, track=(), real=()):
        g = FakePass(buttons, track, real)
        monkeypatch.setattr(battle_pass.capture, "grab", g.grab)
        return g

    return build


def test_the_old_band_held_only_the_top_edge_of_a_lowered_button():
    old_middle = (525 + 565) // 2
    assert old_middle < LOWERED[1]  # the old click went above the button


def test_a_lowered_button_is_clicked_in_its_middle_and_claimed(make):
    g = make([NORMAL, LOWERED, FREE], track=[HEXAGON])
    assert battle_pass.claim_rewards(g) == 3
    assert g.buttons == []
    # left to right in the Golden row, then the Free row, each click in its button's middle
    assert g.clicks == [(507, 575), (768, 553), (768, 958)]
    assert g.lines == [f"Battle pass: reward {i} claimed" for i in (1, 2, 3)]


def test_the_milestone_track_is_not_a_button(make):
    g = make([], track=[HEXAGON, (728, 650, 812, 686)])
    assert battle_pass.claim_rewards(g) == 0
    assert g.clicks == [] and g.wheels == 1


def test_a_button_that_stays_ends_the_visit_after_two_clicks(make):
    g = make([list(LOWERED) + [False], FREE])
    assert battle_pass.claim_rewards(g) == 0
    assert g.clicks == [(507, 575), (507, 575)]
    assert g.lines == ["Battle pass: a Claim button is still there after two clicks, leaving"]
    assert g.diagnostics == ["bp-claim-stays.png"]


def test_a_button_taken_at_the_second_click_counts_once(make):
    g = make([LOWERED])

    real_click = g.click
    first = [True]

    def click():
        if first[0]:  # the first click lands while the page still moves
            first[0] = False
            g.clicks.append(g.pointer)
            return
        real_click()

    g.click = click
    assert battle_pass.claim_rewards(g) == 1
    assert len(g.clicks) == 2 and g.lines == ["Battle pass: reward 1 claimed"]


def test_nothing_in_view_scrolls_once_then_leaves(make):
    g = make([])
    assert battle_pass.claim_rewards(g) == 0
    assert g.wheels == 1 and g.clicks == [] and g.lines == []


def test_the_owners_real_buttons_are_found_and_clicked_in_their_middle(make):
    """The real pixels: at the owner's place (logical top 521) and 22 px lower (under a
    labelled tile), and in the Free row; each click lands in the button's flat middle."""
    g = make([], real=[(918, 521, True), (1441, 543, True), (918, 928, True)])
    assert battle_pass.claim_rewards(g) == 3
    assert g.real == []
    # the colour rows 503..539 of client y (+31): the middle at logical 552 (+22, +407)
    assert g.clicks == [(1008, 552), (1531, 574), (1008, 959)]
