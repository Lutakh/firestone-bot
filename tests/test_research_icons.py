"""Research icons (vision/research_icons.py) on real crops of the owner's 1920x1009 captures
(2026-09-28): tests/fixtures/research-*.npy are the BGR region_image of icon_rect(blob) the bot
reads, the blob as blobs.find_blobs returns it (rounded to its 6 px cells)."""

import json
import os

import numpy as np
import pytest

from firestone_bot import research_data
from firestone_bot.platform.window import Rect
from firestone_bot.vision import blobs, research_icons
from firestone_bot.vision.viewport import Viewport

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
# file, box state, research (None: the icon is cut by the view's left edge). Captures: 71
# (the tree's start, tree XIII), F13_01 (tree XIII one stop on), F01_00 (tree I's start).
CASES = [
    ("research-rage-heroes-available.npy", "available", "Rage Heroes"),  # 71, blob 226, 464
    ("research-energy-heroes-available.npy", "available", "Energy Heroes"),  # 71
    ("research-attribute-damage-running.npy", "running", "Attribute Damage"),  # 71, 1144, 710
    ("research-guardian-power-running.npy", "running", "Guardian Power"),  # F13_01
    ("research-fist-fight-maxed.npy", "maxed", "Fist Fight"),  # F01_00
    ("research-expose-weakness-maxed.npy", "maxed", "Expose Weakness"),  # F13_01, behind the
    ("research-powerless-boss-maxed.npy", "maxed", "Powerless Boss"),  # tab panel from x 1728
    ("research-cut-left-available.npy", "available", None),  # F13_01, Energy Heroes at x 40
]
IDS = [c[0] for c in CASES]


def _load(name: str) -> np.ndarray:
    return np.load(os.path.join(FIX, name))


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_fixture_identified_with_its_state(case):
    name, state, expected = case
    assert research_icons.classify_image(_load(name), state).name == expected


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_fixture_identified_and_its_state_read_from_the_box(case):
    name, state, expected = case
    m = research_icons.classify_image(_load(name))
    assert m.name == expected
    if expected is not None:
        assert m.state == state
        assert m.distance <= research_icons.MAX_DISTANCE  # the HP / DMG pairs: close runner-up


def test_the_exact_corner_is_found_inside_the_blob():
    """The blob is rounded to its cells: the box's own corner is a few px off (Rage Heroes:
    box 225, 467; blob 226, 464)."""
    m = research_icons.classify_image(_load("research-rage-heroes-available.npy"))
    assert (226 + m.dx, 464 + m.dy) == (225, 467)


def test_dark_and_gold_boxes_need_their_own_references():
    """A dark-blue box against the maxed (light-blue) references is not identified."""
    img = _load("research-rage-heroes-available.npy")
    assert research_icons.classify_image(img, "maxed").name is None
    assert research_icons.classify_image(img, "available").name == "Rage Heroes"


def test_hp_and_dmg_pairs_are_told_apart_by_the_pair_stage():
    """Expose Weakness (BOSS HP) and Powerless Boss (BOSS DMG) are 3 to 4 levels apart on
    the full grid; on the cells where they differ, 10 times more."""
    refs = research_icons.default_refs()
    for f, name, other in (
        ("research-expose-weakness-maxed.npy", "Expose Weakness", "Powerless Boss"),
        ("research-powerless-boss-maxed.npy", "Powerless Boss", "Expose Weakness"),
    ):
        img = _load(f)
        rgb = img[..., ::-1]
        corner = research_icons.find_corner(rgb, 1.0, 1.0, research_icons.PAD, research_icons.PAD)
        thumbs = research_icons.window_thumbs(rgb, corner[0], corner[1], 1.0, 1.0)
        ranked = research_icons.rank(thumbs, "maxed", refs)
        assert [ranked[0].name, ranked[1].name] == [name, other]
        assert ranked[1].distance < 3 * ranked[0].distance + 5  # close on the full grid
        p1, p2, n = research_icons.pair_distances(ranked[0], ranked[1])
        assert n >= research_icons.PAIR_MIN_CELLS and p1 < 0.2 * p2


def test_a_smaller_client_reads_the_same_box():
    """The same box captured at 2/3 of the reference scale (a 1280x673 client)."""
    img = _load("research-guardian-power-running.npy").astype(float)
    h, w = img.shape[0] // 3 * 3, img.shape[1] // 3 * 3
    up = np.repeat(np.repeat(img[:h, :w], 2, axis=0), 2, axis=1)
    small = up.reshape(h * 2 // 3, 3, w * 2 // 3, 3, 3).mean(axis=(1, 3)).round().astype(np.uint8)
    assert research_icons.classify_image(small).name == "Guardian Power"


def test_a_sparkle_over_the_icon_never_gives_another_name():
    """A white star over the icon: the name or None (the bot grabs it again), never another."""
    rng = np.random.default_rng(3)
    for name, _, expected in CASES[:7]:
        img = _load(name).copy()
        for _ in range(6):
            x, y = rng.integers(16, 90, size=2)
            spark = img.copy()
            spark[y : y + 30, x + 12 : x + 18] = 255
            spark[y + 12 : y + 18, x : x + 30] = 255
            assert research_icons.classify_image(spark).name in (expected, None)


def test_the_references_cover_every_firestone_research():
    refs = research_icons.default_refs()
    assert set(refs.names) == set(research_data.firestone_names())
    for state in research_icons.STATES:
        assert refs.stacks[state].shape == (len(refs.names), 12, 12, 3)
    assert refs.background.shape == (len(refs.names), 12, 12, 1)
    assert 0.4 < refs.background.mean() < 0.8  # the box's colour around the icons


# --- another capture's colours (review of 2026-09-29) ---------------------------------------
MAC_BLUE = (0x28, 0x48, 0xD8)  # RGB: the Mac's sRGB capture of the dark blue 0x0D49DE
AVAILABLE = CASES[:2]


def _mac_body(img: np.ndarray) -> np.ndarray:
    """The box's dark blue as the Mac's capture reads it, around the icon too; the icon
    untouched."""
    out = img.copy()
    out[research_icons.state_masks(img[..., ::-1])["available"]] = MAC_BLUE[::-1]
    return out


def _cast(img: np.ndarray, rgb=(27, -1, -6)) -> np.ndarray:
    """The whole capture moved by the Mac's offset of the dark blue."""
    return np.clip(img.astype(int) + np.array(rgb[::-1]), 0, 255).astype(np.uint8)


def _display_p3(img: np.ndarray) -> np.ndarray:
    """A model of a capture in Display P3: the sRGB colours converted (it puts 0x0D49DE at
    (33, 72, 214), next to the Mac's 0x2848D8), the icons and every box colour moved."""
    m = np.array([[0.8225, 0.1774, 0.0], [0.0332, 0.9669, 0.0], [0.0171, 0.0724, 0.9108]])
    rgb = img[..., ::-1].astype(np.float64) / 255
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    p3 = np.clip(lin @ m.T, 0, 1)
    enc = np.where(p3 <= 0.0031308, p3 * 12.92, 1.055 * p3 ** (1 / 2.4) - 0.055)
    return np.round(enc * 255)[..., ::-1].astype(np.uint8)


@pytest.mark.parametrize("case", AVAILABLE, ids=IDS[:2])
def test_the_macs_dark_blue_is_corrected(case):
    """Energy Heroes came out None with the Mac's dark blue (11.6 against MAX_DISTANCE 11):
    the references are moved to the box's own colour, each cell by its share of it."""
    name, _, expected = case
    m = research_icons.classify_image(_mac_body(_load(name)))
    assert m.name == expected and m.state == "available"
    assert m.distance <= 6.7  # the Windows self distances
    rng = np.random.default_rng(5)
    for _ in range(6):  # a sparkle still gives the name or None, never another
        x, y = rng.integers(16, 90, size=2)
        spark = _mac_body(_load(name))
        spark[y : y + 30, x + 12 : x + 18] = 255
        spark[y + 12 : y + 18, x : x + 30] = 255
        assert research_icons.classify_image(spark).name in (expected, None)


def test_without_the_masks_the_macs_dark_blue_is_missed():
    with open(research_icons.PATH, encoding="utf-8") as f:
        data = json.load(f)
    del data["masks"]
    img = _mac_body(_load("research-energy-heroes-available.npy"))
    assert research_icons.classify_image(img, None, research_icons.Refs(data)).name is None
    assert research_icons.classify_image(img).name == "Energy Heroes"


@pytest.mark.parametrize("case", AVAILABLE, ids=IDS[:2])
def test_a_uniform_colour_cast_is_corrected(case):
    name, _, expected = case
    assert research_icons.classify_image(_cast(_load(name))).name == expected


@pytest.mark.parametrize("case", CASES[:7], ids=IDS[:7])
def test_a_display_p3_capture_is_identified_in_every_state(case):
    """The light-blue and gold gradients are moved too (the P3 model moves the light blue's
    red by 43 levels: 425 of the owner's 545 maxed boxes came out None, Fist Fight here)."""
    name, state, expected = case
    m = research_icons.classify_image(_display_p3(_load(name)))
    assert (m.name, m.state) == (expected, state)


@pytest.mark.parametrize("case", CASES[:7], ids=IDS[:7])
def test_windows_boxes_are_compared_as_recorded(case):
    """A Windows box reads its colour within the Windows spread: the references are used as
    recorded, the Windows results unchanged."""
    name, state, _ = case
    rgb = _load(name)[..., ::-1]
    pad, icon = research_icons.PAD, research_icons.ICON_W
    body = research_icons.box_body(rgb[pad:, pad + icon :], state)
    refs = research_icons.default_refs()
    assert body is not None
    assert refs.stack(state, body) is refs.stacks[state]


def _rgb(colour: int) -> np.ndarray:
    return np.array([[[(colour >> 16) & 255, (colour >> 8) & 255, colour & 255]]], np.uint8)


def test_box_colours_and_what_is_not_a_box():
    for colour, state in (
        (0x0D49DE, "available"),  # Windows
        (0x2848D8, "available"),  # the Mac's sRGB capture of the same box
        (0x35C0FF, "maxed"),
        (0xFFEB99, "running"),  # the gold's pale top
        (0xDE9E31, "running"),
    ):
        masks = research_icons.state_masks(_rgb(colour))
        assert masks[state][0, 0], hex(colour)
        assert research_icons.box_mask(_rgb(colour))[0, 0]
    # the tree's background, a connector line, text, the slots' green button (the orange gem
    # buttons pass as gold: they sit below the tree area, or on a popup, never scanned)
    for colour in (0x184080, 0x407DD3, 0x29FFFF, 0xFFFFFF, 0x000000, 0x0AA008):
        assert not research_icons.box_mask(_rgb(colour))[0, 0], hex(colour)


class _G:
    """The reference client (logical == screen px) showing one box of each state."""

    def __init__(self):
        self.vp = Viewport(Rect(0, 31, 1920, 1009))
        self.screen = np.zeros((1080, 1920, 3), np.uint8)
        self.screen[:, :] = (0x80, 0x40, 0x18)  # the tree's background, BGR
        for fixture, box, blob, body in (
            ("research-rage-heroes-available.npy", (225, 467), (226, 464), (222, 73, 13)),
            ("research-attribute-damage-running.npy", (1144, 710), (1144, 710), (68, 208, 255)),
        ):
            (x, y), (bx, by) = box, blob
            self.screen[y : y + 101, x : x + 383] = body  # BGR
            self.screen[by - 12 : by + 116, bx - 12 : bx + 124] = _load(fixture)

    def _viewport(self):
        return self.vp

    def grab(self, r):
        return self.screen[r.y : r.y + r.h, r.x : r.x + r.w]

    def region_image(self, rect, anchor=None):
        sx1, sy1 = self.vp.to_screen(rect[0], rect[1], anchor)
        sx2, sy2 = self.vp.to_screen(rect[2], rect[3], anchor)
        return self.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1)).copy()


def test_boxes_are_found_and_identified_through_the_viewport(monkeypatch):
    g = _G()
    monkeypatch.setattr(blobs.capture, "grab", g.grab)
    found = research_icons.find_boxes(g, (40, 110, 1725, 860))
    assert len(found) == 2
    names = sorted(research_icons.identify(g, b).name for b in found)
    assert names == ["Attribute Damage", "Rage Heroes"]
