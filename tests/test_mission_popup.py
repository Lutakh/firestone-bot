"""The world map's mission popups read by their look (vision/mission_popup.py) on real crops
of game 9.1.3a drawn at every client shape (tests/screens.py): the kind of popup, its buttons
inside their true rects, the gem in a paid button, and nothing read on the plain map. And the
centre's look (map_close.look_of / changed) that tells a popup the reader cannot see: every
popup changes it, small changes of the map do not."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from firestone_bot.features import map_close
from firestone_bot.vision import mission_popup as mp
from tests import screens

FIXTURES = Path(__file__).parent / "fixtures"

# look -> (kind, flags)
EXPECT = {
    "start": (mp.START, {"green_gem": False, "orange_gem": True, "gem": True}),
    "start-gem": (mp.START, {"green_gem": True, "orange_gem": True}),
    "start-split": (mp.START, {"green_gem": False, "orange_gem": True}),
    "start-deaf": (mp.START, {"green_gem": False, "orange_gem": True}),
    "start-dark": (mp.UNKNOWN, {}),
    # no price at all in the orange: never seen, not a start popup (its boxes are kept: the
    # bot says it and captures it)
    "start-unpriced": (
        mp.UNKNOWN,
        {"green_gem": False, "orange_gem": False, "orange_label": False},
    ),
    "start-unpriced-nox": (mp.UNKNOWN, {}),
    "start-unpriced-wide": (mp.UNKNOWN, {}),
    "start-label-only": (mp.UNKNOWN, {}),
    "start-swapped": (mp.UNKNOWN, {}),
    "start-no-orange": (mp.UNKNOWN, {}),
    "start-stacked": (mp.UNKNOWN, {}),
    "start-three": (mp.UNKNOWN, {}),
    "start-tall": (mp.UNKNOWN, {}),
    "paid-green-cancel": (mp.UNKNOWN, {}),
    "paid": (
        mp.IN_PROGRESS,
        {"orange_gem": True, "orange_label": True, "cancel_grey": False, "gem": True},
    ),
    "paid-cut": (mp.IN_PROGRESS, {"orange_gem": True, "cancel_grey": False}),
    "paid-label-only": (
        mp.IN_PROGRESS,
        {"orange_gem": False, "orange_label": True, "cancel_grey": False, "gem": False},
    ),
    "paid-plain": (
        mp.IN_PROGRESS,
        {"orange_gem": False, "orange_label": False, "cancel_grey": False},
    ),
    "paid-deadx": (mp.IN_PROGRESS, {"orange_gem": True, "cancel_grey": False}),
    "free": (
        mp.IN_PROGRESS,
        {"orange_gem": False, "orange_label": False, "cancel_grey": True, "gem": False},
    ),
    "free-gem": (mp.IN_PROGRESS, {"orange_gem": True, "cancel_grey": True, "gem": True}),
    "rewards": (mp.REWARDS, {"okay_row_gem": False, "gem": True}),
    "rewards-priced": (mp.REWARDS, {"okay_row_gem": True}),
    "rewards-priced-under": (mp.REWARDS, {"okay_row_gem": True}),
    "rewards-two": (mp.UNKNOWN, {}),
    "rewards-narrow": (mp.UNKNOWN, {}),
    "rewards-x": (mp.UNKNOWN, {}),
    "rewards-three": (mp.UNKNOWN, {}),
    "rewards-cancel": (mp.UNKNOWN, {}),
    "rewards-hollow": (mp.UNKNOWN, {}),
    "rewards-offcentre": (mp.UNKNOWN, {}),
    "rewards-tall": (mp.UNKNOWN, {}),
    # another interface style: no panel read (the centre's look tells them)
    "start+rb": (mp.NONE, {}),
    "paid+rb": (mp.NONE, {}),
    "rewards+rb": (mp.NONE, {}),
    "free-up": (mp.IN_PROGRESS, {"orange_gem": False, "cancel_grey": True}),
    # map art: a small centred cream dialog, a long centred cream bar
    "cream-box": (mp.NONE, {}),
    "cream-bar": (mp.NONE, {}),
    "cream-full": (mp.NONE, {}),
}
# the box read -> the role of the true rect it must fall in, by look
ROLES = {
    "start": {"green": "start", "orange": "paid"},
    "start-gem": {"green": "paid", "orange": "paid"},
    "start-split": {"green": "start", "orange": "paid"},
    "start-deaf": {"green": "dead", "orange": "paid"},
    "start-unpriced": {"green": "start", "orange": "paid"},
    "paid": {"orange": "paid", "cancel": "cancel"},
    "paid-cut": {"orange": "paid", "cancel": "cancel"},
    "paid-label-only": {"orange": "paid", "cancel": "cancel"},
    "paid-plain": {"orange": "paid", "cancel": "cancel"},
    "paid-deadx": {"orange": "paid", "cancel": "cancel"},
    "free": {"orange": "free", "cancel": "cancel"},
    "free-gem": {"orange": "paid", "cancel": "cancel"},
    "free-up": {"orange": "free", "cancel": "cancel"},
    "rewards": {"green": "okay"},
    "rewards-priced": {"green": "paid"},
    "rewards-priced-under": {"green": "paid"},
}
CASES = screens.cases()
# Looks of rules that do not depend on the client's shape (the order and number of the
# buttons, the Okay's place and size, a price painted out), read at four shapes; the others
# at every shape
SOME = {
    "start-deaf",  # read as the start popup (only its Start takes no press)
    "start-unpriced-nox",
    "start-unpriced-wide",
    "start-label-only",
    "start-swapped",
    "start-no-orange",
    "start-stacked",
    "start-three",
    "start-tall",
    "paid-green-cancel",
    "paid-label-only",
    "paid-plain",
    "paid-deadx",
    "rewards-priced-under",
    "rewards-three",
    "rewards-cancel",
    "rewards-hollow",
    "rewards-offcentre",
    "rewards-tall",
    "free-up",  # the never-settling scene's other look: the free popup 30 px higher
}
SOME_CASES = {
    (1920, 1009, "centre"),
    (1600, 1200, "top"),
    (2560, 1080, "centre"),
    (800, 600, "top"),
}


def test_every_look_of_the_bench_has_its_reading():
    assert set(EXPECT) == set(screens.LOOKS)


def _check(scene: screens.Scene, look: str, popup: mp.Popup) -> None:
    kind, flags = EXPECT[look]
    assert popup.kind == kind, (look, popup)
    for name, value in flags.items():
        assert getattr(popup, name) == value, (look, name, popup)
    if kind == mp.NONE:
        assert popup.panel is None, (look, popup)
        return
    for part, role in ROLES.get(look, {}).items():
        box = getattr(popup, part)
        assert any(b.contains(box.cx, box.cy, 0.1) for b in scene.part(role, look)), (part, box)
    parts = screens.LOOKS[look].parts
    if "x" in parts or "deadx" in parts:
        assert popup.close is not None, look
        rings = scene.part("x", look) + scene.part("deadx", look)
        assert any(b.contains(popup.close.cx, popup.close.cy) for b in rings)
    else:
        assert popup.close is None


@pytest.fixture(scope="module", params=CASES, ids=[f"{w}-{h}-{p}" for w, h, p in CASES])
def scene(request):
    """The scene of one client shape and placement, shared by the tests below (pytest runs
    them one shape after the other: the images drawn are reused). Smooth (mean of the
    footprint, bilinear) up to the captures' size, like the game's own anti-aliasing; nearest
    above it: a half-size crop enlarged smoothly is only blurred."""
    w, h, placement = request.param
    mode = "smooth" if screens.k_of(w, h) <= 1.1 else "nearest"
    return screens.Scene(w, h, placement, mode)


def _moved(before: np.ndarray, img: np.ndarray) -> tuple[float, bool]:
    """The share of the centre's blocks that moved from the look `before` to `img`'s
    (map_close.changed's measure), and map_close.changed's answer."""
    now = map_close.look_of(img)
    share = float((np.abs(now - before).mean(axis=2) > map_close.LOOK_LEVELS).mean())
    return share, map_close.changed(before, now)


def test_every_popup_at_every_shape(scene):
    """Each popup read right: its kind and flags, its buttons inside their true rects, its X,
    the tap beside it on the client. And each moves the centre's look by at least twice the
    share map_close.changed needs, the reskinned ones the reader cannot see too: a popup
    of a look the reader does not know is told by it (0.28 measured at least: the reskinned
    Mission Rewards at 800x600 and 1280x1024)."""
    # the plain map: the owner's, with missions running, the list, the idle banner and the
    # desert, and the map's look-alikes drawn next to where the popups sit
    base = scene.client_image(None)
    assert mp.read(base).kind == mp.NONE
    before = map_close.look_of(base)
    some = (scene.w, scene.h, scene.placement) in SOME_CASES
    for look, drawn in screens.LOOKS.items():
        if look == "free-up" and not some:
            continue  # free's look 30 px higher, drawn again from its crops: four shapes
        img = scene.client_image(look)
        if drawn.popup:
            share, changed = _moved(before, img)
            assert share >= 2 * map_close.LOOK_CHANGED and changed, (look, share)
        if look in SOME and not some:
            continue
        popup = mp.read(img)
        _check(scene, look, popup)
        if popup.panel is not None:
            # the tap that closes a popup without an X lands beside it, on the client
            x, y = popup.outside()
            assert not scene.panel(look).contains(x, y) and 0 <= x < scene.w and 0 <= y < scene.h


BANNER = (460, 942, 1244, 996)  # "Your squads are idling! Start a new mission."


def _copy(scene, img, src, dst) -> np.ndarray:
    """`img` with the client px of reference rect `src` copied onto `dst` (the same size)."""
    out = img.copy()
    a, b = scene.to_screen(src), scene.to_screen(dst)
    ax, ay = round(a.x1 - scene.client.x), round(a.y1 - scene.client.y)
    bx, by = round(b.x1 - scene.client.x), round(b.y1 - scene.client.y)
    w = min(round(b.x2 - b.x1), scene.w - max(ax, bx))
    h = min(round(b.y2 - b.y1), scene.h - max(ay, by))
    out[by : by + h, bx : bx + w] = img[ay : ay + h, ax : ax + w]
    return out


def _fill(scene, img, rect, bgr) -> np.ndarray:
    out = img.copy()
    scene._fill(out, rect, bgr)
    return out


def test_small_changes_of_the_map_leave_its_look(scene):
    """What changes on the map between a click and the reads after it is no popup: the idle
    banner shown or gone (a start takes the last idle squads, a claim frees some), a mission
    label's digits, an icon, the mission list gone, the map moved by a pixel or two. Each
    moves less than half the share map_close.changed needs."""
    base = scene.client_image(None)
    before = map_close.look_of(base)
    x1, y1, x2, y2 = BANNER
    small = {
        # the banner gone, the map under it (the rows above it, carried down)
        "idle banner": _copy(scene, base, (x1, 2 * y1 - y2, x2, y1), BANNER),
        "label digits": _fill(scene, base, (930, 600, 990, 620), (255, 255, 255)),
        # the last mission claimed: the list at the left goes (the band is the centre's)
        "mission list gone": _fill(scene, base, (0, 180, 275, 1009), screens.SEA),
        **{
            f"icon at {x},{y}": _fill(scene, base, (x, y, x + 60, y + 60), (60, 66, 231))
            for x, y in ((931, 519), (1180, 300))
        },
        **{
            f"map moved {dx},{dy}": np.roll(base, (dy, dx), axis=(0, 1))
            for dx, dy in ((1, 1), (-2, 2))
        },
    }
    for what, img in small.items():
        share, changed = _moved(before, img)
        assert share < map_close.LOOK_CHANGED / 2 and not changed, (what, share)


def test_the_idle_banner_over_open_sea(scene):
    """The banner's worst case: gone from over open sea (the most contrast under it). Never
    a popup for map_close.changed; measured 0.073..0.076 at the 16:9 to 21:9 shapes and the
    taller ones with the popups centred, against LOOK_CHANGED / 2 = 0.06 (0.038..0.049
    elsewhere): reported as an expected failure with its share, the margin not loosened."""
    base = scene.client_image(None)
    share, changed = _moved(map_close.look_of(base), _fill(scene, base, BANNER, screens.SEA))
    assert share < map_close.LOOK_CHANGED and not changed, share
    if share >= map_close.LOOK_CHANGED / 2:
        pytest.xfail(f"the banner over open sea moves {share:.3f} of the centre (half: 0.06)")


@pytest.mark.parametrize(("w", "h", "placement"), [(1920, 1009, "centre"), (1600, 1200, "top")])
@pytest.mark.parametrize("cast", [(8, 8, 8), (-8, -8, -8), (8, 0, -8), (-8, 8, 0), (0, 8, -8)])
def test_a_colour_cast_of_8_changes_nothing(w, h, placement, cast):
    """macOS colour management shifts the capture's colours by a few levels."""
    for look in ("start", "paid", "free", "rewards"):
        scene = screens.Scene(w, h, placement, "nearest", cast=cast)
        _check(scene, look, mp.read(scene.client_image(look)))
    assert mp.read(scene.client_image(None)).kind == mp.NONE


def test_boxes_are_screen_px_of_a_client_inside_a_larger_screen():
    (w, h), origin, screen = screens.OFFSET
    scene = screens.Scene(w, h, "centre", "nearest", origin=origin, screen=screen)
    scene.popup = "start"
    c = scene.client
    popup = mp.read(scene.grab(c)[:, :, :3], (c.x, c.y))
    _check(scene, "start", popup)
    assert popup.panel.x1 > origin[0] and popup.panel.y1 > origin[1]


def test_the_measured_shape_of_the_start_popup():
    """At the owner's 1920x1009 the panel is 1098 px wide: the ruler every other share is
    taken from."""
    scene = screens.Scene(1920, 1009)
    popup = mp.read(scene.client_image("start"))
    assert abs(popup.panel.w - 1098) <= 16 and abs(popup.panel.cx - 960) <= 2
    assert abs(popup.green.w / popup.panel.w - 0.23) <= 0.02


def test_two_reads_of_a_popup_scaling_in_differ():
    """A popup caught while it scales in reads smaller than once it is there: not the same
    read (map_close.read_popup waits for two alike)."""
    small = screens.Scene(1280, 720)
    full = screens.Scene(1920, 1009)
    a = mp.read(small.client_image("start"))
    b = mp.read(full.client_image("start"))
    assert a.kind == b.kind == mp.START
    assert not a.same_as(b) and b.same_as(mp.read(full.client_image("start")))


def test_a_grey_line_above_the_cancel_is_no_part_of_it():
    """The World domination event's mystery mission on the owner's 1920x1009 client (2026-10-31
    04:54): 1:58 left, so the free layout, but its progress bar still mostly empty, and the
    bar's grey top line runs across the grey Cancel's columns 74 px above it. Taken in, the
    Cancel was 156 px tall, no button: the popup read unknown, its free speed-up was missed.
    Client x 940..1220, y 604..804 of the capture; the panel is 1104 px wide."""
    crop = np.load(FIXTURES / "mission-free-short-cancel-1920x1009.npz")["crop"]
    (box,) = mp._boxes(mp.grey_mask(crop), 1, 1104, 940, 604)
    assert abs(box.x1 - 956) <= 4 and abs(box.x2 - 1210) <= 4
    assert abs(box.y1 - 697) <= 4 and abs(box.y2 - 783) <= 8


def test_the_tap_beside_a_panel_is_never_off_the_client():
    """A cream panel as wide as the client (a foreign window, cream map art on both sides):
    no point beside it on the client, so none (map_close then stops rather than tap another
    window)."""
    client = mp.Box(0, 0, 1920, 1080)
    wide = mp.Popup(kind=mp.UNKNOWN, panel=mp.Box(50, 200, 1870, 900), client=client)
    assert wide.outside() is None
    narrow = mp.Popup(kind=mp.UNKNOWN, panel=mp.Box(411, 187, 1509, 897), client=client)
    assert narrow.outside() == (1509 + round(0.05 * 1098), 542)
    assert mp.Popup(kind=mp.UNKNOWN, panel=mp.Box(50, 200, 1870, 900)).outside() is not None
