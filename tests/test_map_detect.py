"""Mission detection on the world map: outlined white duration labels."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from firestone_bot.features import map_align, map_detect
from firestone_bot.platform.window import Rect
from firestone_bot.vision.viewport import Viewport

REF = Viewport(Rect(0, 0, 1920, 1009))  # the reference client: every anchor agrees
NOT_MEASURED = MappingProxyType({})  # Game.vars before the landmark measured the map's scale


def _digit(img, x, y, w=12, h=18):
    """A white block with a 2 px dark outline, like one bold digit."""
    img[y - 2 : y + h + 2, x - 2 : x + w + 2] = (40, 40, 40)
    img[y : y + h, x : x + w] = (255, 255, 255)


def _label(img, x, y, digits=4):
    for i in range(digits):
        _digit(img, x + i * 16, y)


def test_labels_found_and_isolated_shapes_ignored():
    img = np.full((400, 600, 3), (60, 120, 200), np.uint8)
    _label(img, 100, 100)  # "27:36"-like row of four digits
    _label(img, 400, 300, digits=3)  # "4:57"-like
    _digit(img, 300, 200)  # a single outlined block: not a label
    img[20:40, 500:560] = (255, 255, 255)  # plain white without outline: ignored
    labels = map_detect.find_labels(img, 1.0)
    assert len(labels) == 2
    (x0, y0, x1, y1), (a0, b0, _a1, _b1) = sorted(labels)
    assert (x0, y0) == (100, 100) and x1 == 100 + 3 * 16 + 12 and y1 == 118
    assert (a0, b0) == (400, 300)


def test_find_missions_maps_labels_to_logical_icon_centres():
    x1, y1, x2, y2 = map_detect.atlas.MAP_DETECT_AREA
    img = np.full((y2 - y1, x2 - x1, 3), (60, 120, 200), np.uint8)  # 1 px per logical px
    _label(img, 200, 400)

    class G:
        vars = NOT_MEASURED

        def _viewport(self):
            return REF

        def region_image(self, rect):
            assert rect == map_detect.atlas.MAP_DETECT_AREA
            return img

    (x, y), *rest = map_detect.find_missions(G())
    assert not rest
    assert x == x1 + int((200 + 200 + 3 * 16 + 12) / 2)
    assert y == y1 + 409 - map_detect.atlas.MAP_LABEL_TO_ICON


def test_half_pixel_labels_give_the_points_of_0_3_34_on_the_reference_client():
    """MapState remembers the clicked points by exact value: a label centre on a half pixel
    is floored as before (review 2026-10-28: rounded, a third of the points moved by 1)."""
    img = np.full((800, 1600, 3), (60, 120, 200), np.uint8)
    for i in range(4):
        _digit(img, 201 + i * 16, 401, w=13, h=19)  # 61 x 19: the centre on half pixels

    class G:
        vars = NOT_MEASURED

        def _viewport(self):
            return REF

        def region_image(self, rect):
            return img

    ((x, y),) = map_detect.find_missions(G())
    x1, y1, _, _ = map_detect.atlas.MAP_DETECT_AREA
    assert (x, y) == (
        x1 + int(201 + 61 / 2),
        y1 + int(401 + 19 / 2) - map_detect.atlas.MAP_LABEL_TO_ICON,
    )


def test_panel_labels_are_not_missions():
    """The remaining-time labels of the left HUD panel (running missions) are dropped."""
    img = np.full((800, 1600, 3), (60, 120, 200), np.uint8)
    _label(img, 40, 150)  # far left: the panel
    _label(img, 600, 400)  # on the map

    class G:
        vars = NOT_MEASURED

        def _viewport(self):
            return REF

        def region_image(self, rect):
            return img

    points = map_detect.find_missions(G())
    assert len(points) == 1 and points[0][0] > map_detect.PANEL_MAX_X


def test_points_are_clicked_on_their_label_at_16_9():
    """1920x1080 client: the area's corners follow the HUD edges, the map is centred. A label
    at client x 630 was clicked at 674 (report ANHNX9, 2026-10-25: up to 45 px beside the
    icon); the point now maps back, centre-anchored, onto the label's own column."""
    vp = Viewport(Rect(0, 0, 1920, 1080))
    x1, y1, x2, y2 = map_detect.atlas.MAP_DETECT_AREA
    sx1, sy1 = vp.to_screen(x1, y1)
    sx2, sy2 = vp.to_screen(x2, y2)
    img = np.full((sy2 - sy1, sx2 - sx1, 3), (60, 120, 200), np.uint8)
    _label(img, 493, 400)  # centre at client x 107 + 523 = 630
    _label(img, 20, 150)  # the left HUD panel (client x 157): not a mission

    class G:
        vars = NOT_MEASURED

        def _viewport(self):
            return vp

        def region_image(self, rect):
            return img

    ((x, y),) = map_detect.find_missions(G())
    cx, _ = vp.to_screen(x, y, map_detect.atlas.ANCHOR_CENTER)
    assert abs(cx - (sx1 + 493 + 30)) <= 1


# Report G8N62Y (2026-10-30, Steam, client 1920x1017, the map dragged down by the detection
# pass): client x 1190..1500, y 20..104 of 20261030-143600-map-no-icon.png. It holds the
# squads and honor counters (labels to find_labels, client y 27..45) and the label "4:24:32"
# of the Doomfire Island mission (client 1269..1317 x 85..95), the only mission left.
NORTH = np.load(Path(__file__).parent / "fixtures" / "map-north-label-under-hud-1920x1017.npy")
SEA = (146, 66, 18)  # BGR, the open sea of the same capture


def _sea_game(w, h, pastes):
    """A client of w x h px of open sea with crops pasted at their client (x, y), read like
    Game.region_image (one default anchor per corner)."""
    vp = Viewport(Rect(0, 0, w, h))
    screen = np.empty((h, w, 3), np.uint8)
    screen[:] = SEA
    for crop, x, y in pastes:
        screen[y : y + crop.shape[0], x : x + crop.shape[1]] = crop

    class G:
        vars = NOT_MEASURED

        def _viewport(self):
            return vp

        def region_image(self, rect):
            x1, y1 = vp.to_screen(rect[0], rect[1])
            x2, y2 = vp.to_screen(rect[2], rect[3])
            return screen[y1:y2, x1:x2]

    return G(), vp


def _north_game(dy=0):
    """The 1920x1017 client of report G8N62Y with the fixture at its place, `dy` px lower."""
    return _sea_game(1920, 1017, [(NORTH, 1190, 20 + dy)])


def test_a_mission_at_the_north_edge_is_found_under_the_hud_counters(monkeypatch):
    """The label sat at client y 89, above the old area (top 160 = client 129): every cycle
    the bot dragged the map, saw nothing and searched again, for hours. The counters above it
    read as labels too and stay out (they end at client y 45)."""
    g, vp = _north_game()
    ((x, y),) = map_detect.find_missions(g)
    sx, sy = vp.to_screen(x, y, map_detect.atlas.ANCHOR_CENTER)
    assert abs(sx - 1293) <= 1 and 60 <= sy <= 80  # the volcano icon, above its label
    monkeypatch.setattr(map_detect.atlas, "MAP_DETECT_AREA", (100, 160, 1700, 960))
    assert map_detect.find_missions(g) == []  # 0.3.35's area


def test_a_label_whose_icon_is_under_a_counter_is_left():
    """A label 12 px higher is still inside the area, but its icon would be clicked on the
    squads counter (bottom edge MAP_DETECT_HUD_BOTTOM)."""
    g, _vp = _north_game(dy=-12)
    x1, y1, x2, y2 = map_detect.atlas.MAP_DETECT_AREA
    labels = map_detect.find_labels(g.region_image((x1, y1, x2, y2)), 1.0)
    assert len(labels) == 1  # found by its look...
    assert map_detect.find_missions(g) == []  # ...and left


# The owner's 1920x1009 client (captures map_clean.png, client x 180..560, y 85..130: the rank
# title and the XP numbers "6796 / 17500", which find_labels reads as a label) and
# map_issue.png (client x 455..510, y 148..170: the "21:23" label of a mission just right of
# the avatar block).
AVATAR = np.load(Path(__file__).parent / "fixtures" / "map-avatar-xp-1920x1009.npy")
NEAR = np.load(Path(__file__).parent / "fixtures" / "map-label-near-avatar-1920x1009.npy")


def test_the_xp_numbers_under_the_avatar_are_no_mission(monkeypatch):
    """The area's new top reaches the XP bar: only MAP_DETECT_AVATAR keeps it out, and it
    must not reach the mission just beside it."""
    g, _vp = _sea_game(1920, 1009, [(AVATAR, 180, 85), (NEAR, 455, 148)])
    x1, y1, x2, y2 = map_detect.atlas.MAP_DETECT_AREA
    assert len(map_detect.find_labels(g.region_image((x1, y1, x2, y2)), 1.0)) == 2
    assert map_detect.find_missions(g) == [(482, 172)]
    monkeypatch.setattr(map_detect.atlas, "MAP_DETECT_AVATAR", (0, 0))
    assert map_detect.find_missions(g) == [(380, 120), (482, 172)]


def test_a_label_whose_icon_is_under_the_info_button_is_left():
    """A map left 74..86 px too high (alignment given up) put a label under the green "i"
    beside the rank title: the click would open the rank info. Found again lower once the
    map is dragged down, like before the area grew."""
    img = np.empty((50, 800, 3), np.uint8)
    img[:] = SEA
    _label(img, 10, 10)  # client centre x 592 once pasted at x 552
    _label(img, 711, 10)  # client centre x 1293
    g, vp = _sea_game(1920, 1009, [(img, 552, 66)])
    ((x, y),) = map_detect.find_missions(g)
    assert abs(vp.to_screen(x, y, map_detect.atlas.ANCHOR_CENTER)[0] - 1293) <= 1


def test_thresholds_follow_the_capture_factor():
    """Retina-like capture: digits twice as tall are still labels with factor 2."""
    img = np.full((400, 600, 3), (60, 120, 200), np.uint8)
    for i in range(4):
        _digit(img, 100 + i * 32, 100, w=24, h=36)
    assert map_detect.find_labels(img, 1.0) == []
    assert len(map_detect.find_labels(img, 2.0)) == 1


def _split(img, x, y, w=6, top=4, gap=1, bottom=5):
    """A "5" cut in two by anti-aliasing: two outlined white halves, `gap` rows apart."""
    h = top + gap + bottom
    img[y - 2 : y + h + 2, x - 2 : x + w + 2] = (40, 40, 40)
    img[y : y + top, x : x + w] = (255, 255, 255)
    img[y + top + gap : y + h, x : x + w] = (255, 255, 255)


def test_a_label_of_split_digits_is_found():
    """ "15:55" (owner, 2026-10-27): a whole "1" and three "5"s cut in two by anti-aliasing.
    With a single whole digit the label was dropped and its mission waited 35 minutes."""
    img = np.full((200, 300, 3), (60, 120, 200), np.uint8)
    _digit(img, 100, 100, w=4, h=10)
    _split(img, 107, 100)
    _split(img, 119, 100)
    _split(img, 127, 100)
    assert map_detect.find_labels(img, 1.0) == [(100, 100, 133, 110)]
    # twice the size (a Retina capture): halves twice as tall, two rows apart
    img = np.full((400, 600, 3), (60, 120, 200), np.uint8)
    _digit(img, 200, 200, w=8, h=20)
    for x in (214, 238, 254):
        _split(img, x, 200, w=12, top=8, gap=2, bottom=10)
    assert len(map_detect.find_labels(img, 2.0)) == 1


def test_split_shapes_alone_are_not_labels():
    img = np.full((200, 300, 3), (60, 120, 200), np.uint8)
    _split(img, 100, 100)  # a lone split digit
    assert map_detect.find_labels(img, 1.0) == []
    img = np.full((200, 300, 3), (60, 120, 200), np.uint8)
    _split(img, 100, 100, w=12)  # wide halves (a star cut in two): wider than tall once joined
    _split(img, 116, 100, w=12)
    _digit(img, 132, 100, w=4, h=10)
    assert map_detect.find_labels(img, 1.0) == []


# --- the size of the labels: the scale the map is drawn at (review of 8558a26) ----------------
@pytest.mark.parametrize(
    ("client", "scale", "factor"),
    [
        ((1920, 1009), None, 1.0),  # the owner's client: as before, exactly
        ((1920, 1009), 1.0, 1.0),
        ((1920, 1080), map_align.FITTED_SCALE, 1.0),  # ANHNX9: a map fitted at 16:9 (0.986)
        ((2560, 1080), 1.0, 1.070),  # 21:9: the area's stretched width said 1.386
        ((3440, 1440), 1.0, 1.427),  # 1.864 by the area
        ((1366, 768), map_align.FITTED_SCALE, 0.711),  # a game started at 1366x768 (0.702)
        ((1366, 768), None, 0.761),  # before the landmark measured it: the client's alone
    ],
)
def test_the_labels_are_sized_by_the_scale_the_map_is_drawn_at(monkeypatch, client, scale, factor):
    """find_labels' thresholds follow the map, not the detection area: its corners follow
    the HUD edges and stretch with the client's shape (1 label of 27 found at 2560x1080 in
    the review's synthetic test, 11 with the map's scale, 27 drawn crisp)."""
    vp = Viewport(Rect(0, 0, *client))
    seen = []
    monkeypatch.setattr(map_detect, "find_labels", lambda img, f: seen.append(f) or [])

    class G:
        vars = NOT_MEASURED if scale is None else MappingProxyType({map_align.SCALE_KEY: scale})

        def _viewport(self):
            return vp

        def region_image(self, rect):
            return np.zeros((10, 10, 3), np.uint8)

    assert map_detect.find_missions(G()) == [] and seen == [factor]


def _thin_digit(img, x, y, w=2, h=7, white=230):
    """A digit as a map drawn at about 2/3 of the reference size shows it: a 2 px stroke whose
    white blends with its 1 px dark outline (under WHITE_MIN, the outline 2 px away)."""
    img[y - 2 : y + h + 2, x - 2 : x + w + 2] = (40, 40, 40)
    img[y - 1 : y + h + 1, x - 1 : x + w + 1] = (150, 150, 150)
    img[y : y + h, x : x + w] = (white, white, white)


def _thin_label(img, x, y, digits=4):
    for i in range(digits):
        _thin_digit(img, x + i * 8, y)


def test_thin_digits_of_a_small_map_are_a_label(monkeypatch):
    """1280x720 (a game started there: 0.667): the label is read with the small-map white
    and the 2 px reach; with either of the reference ones it is not (the review of 8558a26
    found 1 label of 27 at that size). The same shapes are no label at the reference size,
    where nothing changed, and a bright stroke without an outline (snow, a cloud) is none."""
    img = np.full((60, 120, 3), (60, 120, 200), np.uint8)
    _thin_label(img, 20, 20)
    img[40:47, 80:82] = (230, 230, 230)  # bright, no outline
    img[40:47, 88:90] = (230, 230, 230)
    assert map_detect.find_labels(img, 0.667) == [(20, 20, 46, 27)]
    assert map_detect.find_labels(img, 1.0) == []
    monkeypatch.setattr(map_detect, "OUTLINE_MIN_PX", 1)
    assert map_detect.find_labels(img, 0.667) == []
    monkeypatch.setattr(map_detect, "OUTLINE_MIN_PX", 2)
    monkeypatch.setattr(map_detect, "SMALL_SCALE", 0.0)  # WHITE_MIN at every size
    assert map_detect.find_labels(img, 0.667) == []


def _shrunk(img, k):
    """`img` drawn k times smaller (each pixel the mean of its footprint, like a smaller
    render of the same art)."""
    from tests import screens

    h, w = img.shape[:2]
    out = screens.resample(img, 0, 0, 1 / k, round(w * k), round(h * k), "smooth")
    return np.rint(out).clip(0, 255).astype(np.uint8)


def test_a_real_label_of_a_small_map_is_read(monkeypatch):
    """The "21:23" label of the owner's map (map_issue.png) drawn at the sizes of the small
    clients (1366x768 fitted 0.711, 1280x720 0.714 / 0.667, a maximised 1366x768 window
    0.699, 0.65): read at every one; with the reference thresholds it was lost at some."""
    sizes = (0.75, 0.714, 0.711, 0.7, 0.699, 0.667, 0.65)
    for k in sizes:
        assert len(map_detect.find_labels(_shrunk(NEAR, k), k)) == 1, k
    monkeypatch.setattr(map_detect, "OUTLINE_MIN_PX", 1)
    monkeypatch.setattr(map_detect, "SMALL_SCALE", 0.0)
    assert any(not map_detect.find_labels(_shrunk(NEAR, k), k) for k in sizes)
