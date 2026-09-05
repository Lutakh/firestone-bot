"""Pure geometry of the macOS backend (points <-> physical pixels, title bar, Retina crop).

No pyobjc needed: only the functions that do not touch Quartz / AppKit are exercised, so the
tests run on every OS (CI is ubuntu).
"""

import numpy as np

from firestone_bot.platform.capture import mac_points_request
from firestone_bot.platform.mac.window import (
    bar_sizes,
    client_rect,
    is_fullscreen,
    title_bar_rows,
    to_pixels,
)
from firestone_bot.platform.types import Rect


def test_to_pixels_scales_by_backing_factor():
    assert to_pixels(10, 33, 1512, 949, 2.0) == Rect(20, 66, 3024, 1898)
    assert to_pixels(10, 33, 1512, 949, 1.0) == Rect(10, 33, 1512, 949)


def test_client_rect_removes_title_bar_unless_fullscreen():
    outer = Rect(0, 66, 3024, 1898)
    assert client_rect(outer, 56, False) == Rect(0, 122, 3024, 1842)
    assert client_rect(outer, 56, True) == outer
    assert client_rect(Rect(0, 0, 100, 40), 56, False).h == 0  # never negative


def test_is_fullscreen_covers_screen_or_screen_minus_menu_bar():
    assert is_fullscreen(0, 0, 1512, 982, 1512, 982)
    assert is_fullscreen(0, 33, 1512, 949, 1512, 982)  # fullscreen Space, menu bar shown
    assert not is_fullscreen(0, 65, 1512, 883, 1512, 982)  # zoomed window (title bar kept)
    assert not is_fullscreen(100, 100, 1280, 720, 1512, 982)


def test_mac_points_request_snaps_to_points_and_crops_back():
    req, ox, oy = mac_points_request(Rect(0, 66, 3024, 1898), 2.0)
    assert req == {"left": 0, "top": 33, "width": 1512, "height": 949} and (ox, oy) == (0, 0)
    # odd pixel rect: request grows to whole points, offset points at the requested pixel
    req, ox, oy = mac_points_request(Rect(101, 67, 7, 5), 2.0)
    assert req == {"left": 50, "top": 33, "width": 4, "height": 3}
    assert (ox, oy) == (1, 1)
    assert ox + 7 <= req["width"] * 2 and oy + 5 <= req["height"] * 2
    # factor 1 is the identity
    assert mac_points_request(Rect(3, 4, 5, 6), 1.0) == (
        {"left": 3, "top": 4, "width": 5, "height": 6},
        0,
        0,
    )


def test_bar_sizes_needs_every_strip_black_and_rejects_huge_bars():
    n = 100
    a = np.zeros(n, bool)
    a[:10] = True
    a[-7:] = True
    b = a.copy()
    b[3] = False  # one strip sees content in the top bar: bar stops there
    assert bar_sizes([a, a], n) == (10, 7)
    assert bar_sizes([a, b], n) == (3, 7)
    assert bar_sizes([np.ones(n, bool)], n) == (0, 0)  # all black = loading screen, no bars
    assert bar_sizes([], n) == (0, 0)


def test_title_bar_rows_counts_flat_rows_and_separator():
    img = np.full((200, 400, 4), 60, np.uint8)  # flat title bar colour
    img[56] = 0  # separator line
    img[57:] = np.random.default_rng(1).integers(0, 255, (143, 400, 4), dtype=np.uint8)
    img[:60, :40] = 200  # traffic lights on the left are ignored (middle 60 % only)
    img[0] = 94  # light border line on top
    img[16:32, 180:220] = 230  # title text in the middle
    assert title_bar_rows(img, 36, 80) == 57
    assert title_bar_rows(img, 60, 80) is None  # outside the plausible range
    assert title_bar_rows(img[57:], 36, 80) is None  # no bar at all
