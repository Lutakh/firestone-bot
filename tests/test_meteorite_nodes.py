"""Meteorite tree reader (vision/meteorite_nodes.py) on the owner's captures (2026-09-28, Epic
1920x1009, tree X): node crops (maxed Raining Gold 30, not maxed Tank Specialization 6 and
Attribute Armor 0), level labels, the counter, the popup's cost and icon (BGR, as
Game.region_image returns them).

The lines are tested on a tree put together from the real node crops: a start and three
chains of four, joined by lines of the game's line colour, at full and half size."""

import json
from pathlib import Path

import numpy as np
import pytest

from firestone_bot import research_data
from firestone_bot.features import meteorite, token_counter
from firestone_bot.vision import atlas
from firestone_bot.vision import meteorite_nodes as mn
from firestone_bot.vision.digits import DigitReader

FIX = Path(__file__).parent / "fixtures"
REFS = mn.references()
NODE_CROPS = {
    "meteorite-node-maxed-raining-gold-30": (True, 30, "Raining Gold"),
    "meteorite-node-not-maxed-tank-6": (False, 6, "Tank Specialization"),
    "meteorite-node-not-maxed-armor-0": (False, 0, "Attribute Armor"),
}


class Reader:
    reader = DigitReader()

    def digit_reader(self):
        return self.reader


def _read(crop):
    return token_counter.read_image(Reader(), crop)


def _rgb(name):
    return np.ascontiguousarray(np.load(FIX / f"{name}.npy")[:, :, ::-1])


@pytest.mark.parametrize("name", sorted(NODE_CROPS))
def test_a_node_is_found_with_its_state_level_and_research(name):
    maxed, level, research = NODE_CROPS[name]
    img = _rgb(name)
    nodes = mn.detect_nodes(img, 1.0)
    assert len(nodes) == 1
    n = nodes[0]
    assert abs(n.cx - 70) <= 2 and abs(n.cy - 70) <= 2
    assert n.maxed is maxed
    mn.read_levels(img, nodes, 1.0, _read)
    assert n.level == level
    got, d1, d2, _ = REFS.classify(mn.icon_integral(img), n.cx, n.cy, 1.0)
    assert got == research and d1 < 4 and d2 > 20


def test_the_state_is_the_disc_colour_not_the_ring():
    """The maxed crop with its glowing disc painted the not-maxed navy reads as not maxed,
    and its icon still matches (the background mask removes both discs)."""
    img = _rgb("meteorite-node-maxed-raining-gold-30").astype(np.float32)
    n = mn.detect_nodes(img.astype(np.uint8), 1.0)[0]
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    disc = np.hypot(yy - n.cy, xx - n.cx) < 46
    bg = ((img[:, :, 2] - img[:, :, 0]) >= 70) & (img[:, :, 2] >= 100)
    dark = img.copy()
    dark[disc & bg] = (33, 56, 141)  # the not-maxed disc colour
    dark = dark.astype(np.uint8)
    found = mn.detect_nodes(dark, 1.0)
    assert len(found) == 1 and found[0].maxed is False
    got, *_ = REFS.classify(mn.icon_integral(dark), found[0].cx, found[0].cy, 1.0)
    assert got == "Raining Gold"


@pytest.mark.parametrize(
    "name, value",
    [
        ("meteorite-level-0", 0),
        ("meteorite-level-6", 6),
        ("meteorite-level-25", 25),
        ("meteorite-level-30", 30),
        ("meteorite-counter-1242", 1242),  # "1,242": the comma is too small to be a glyph
        ("meteorite-popup-cost-750", 750),
    ],
)
def test_numbers(name, value):
    assert token_counter.read_image(Reader(), np.load(FIX / f"{name}.npy")) == value


def _old_place(c):
    """The icon at the centre `c` of a crop of METEORITE_POPUP_ICON_RECT, before 9.1.3a."""
    return ((c, c, mn.POPUP_ICON_SCALE),)


def _band_places(img):
    """Both icon places in a crop of METEORITE_POPUP_ICON_BAND, and the crop's scale."""
    band = atlas.METEORITE_POPUP_ICON_BAND
    s = img.shape[1] / (band[2] - band[0])
    places = [((x - band[0]) * s, (y - band[1]) * s, k) for x, y, k in atlas.METEORITE_POPUP_ICONS]
    return places, s


def _half(img):
    h, w = img.shape[0] // 2 * 2, img.shape[1] // 2 * 2
    return img[:h, :w].reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3)).astype(np.uint8)


def test_the_popup_icon_is_the_node_icon_drawn_bigger():
    """Capture of METEORITE_POPUP_ICON_RECT with Tank Specialization's popup open."""
    img = _rgb("meteorite-popup-icon-tank")
    got, d, _ = mn.popup_research(REFS, img, _old_place(60), 1.0)
    assert got == "Tank Specialization" and d < 4
    ten = frozenset(research_data.meteorite_names_of("10"))
    assert mn.popup_research(REFS, img, _old_place(60), 1.0, ten)[0] == "Tank Specialization"
    # at half the size (a 960 px wide client)
    half = img[:120, :120].reshape(60, 2, 60, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
    got, d, _ = mn.popup_research(REFS, half, _old_place(30), 0.5)
    assert got == "Tank Specialization" and d < 8
    # the tree itself, read as a popup, is not taken for a research
    blank = np.zeros_like(img)
    blank[:] = (41, 170, 247)
    assert mn.popup_research(REFS, blank, _old_place(60), 1.0)[0] is None


def test_the_old_popup_still_reads_in_the_band():
    """The tank crop of before 9.1.3a put back in METEORITE_POPUP_ICON_BAND on its panel."""
    old = _rgb("meteorite-popup-icon-tank")
    band, r = atlas.METEORITE_POPUP_ICON_BAND, atlas.METEORITE_POPUP_ICON_RECT
    img = np.empty((band[3] - band[1], band[2] - band[0], 3), np.uint8)
    img[:] = old[0, 0]  # the popup's panel
    img[r[1] - band[1] : r[3] - band[1], r[0] - band[0] : r[2] - band[0]] = old
    places, s = _band_places(img)
    got, d, _ = mn.popup_research(REFS, img, places, s)
    assert got == "Tank Specialization" and d < 4
    half = _half(img)
    places, s = _band_places(half)
    assert mn.popup_research(REFS, half, places, s)[0] == "Tank Specialization"


@pytest.mark.parametrize(
    "name, research, tree, most",
    [
        # the owner's Epic client, 1920x1009, 2026-10-28: no disc, 1.43 x, centred (708, 336)
        ("meteorite-popup-band-all-attributes-913a", "All Attributes", "11", 4),
        # report ANHNX9, Steam, 1920x1080 (scale 1.07), 2026-10-25: the coins' light rays show
        ("meteorite-popup-band-raining-gold-913a", "Raining Gold", "6", 14),
    ],
)
def test_the_913a_popup_icon_is_named(name, research, tree, most):
    img = _rgb(name)
    for names in (None, frozenset(research_data.meteorite_names_of(tree))):
        places, s = _band_places(img)
        got, d, closest = mn.popup_research(REFS, img, places, s, names)
        assert got == closest == research and d < most
    half = _half(img)
    places, s = _band_places(half)
    assert mn.popup_research(REFS, half, places, s)[0] == research
    # 0.3.34 read only the old place: nothing within the limit
    places, s = _band_places(img)
    got, d, _ = mn.popup_research(REFS, img, places[:1], s)
    assert got is None and d > 30


def test_a_loose_popup_match_needs_a_clear_runner_up():
    """Raining Gold's 9.1.3a icon (12-13 from its reference) is named only because every
    other name is 3 x as far: beside a look-alike reference 6 away it is not named."""
    img = _rgb("meteorite-popup-band-raining-gold-913a")
    places, s = _band_places(img)
    ref = REFS.refs["Raining Gold"]
    near = ref.copy()
    near[:, :, 3] = np.clip(near[:, :, 3] + 24, 0, 255)  # coverage +24: 6 apart (mean of 4)
    refs = mn.IconRefs({"Raining Gold": ref, "Look-alike": near})
    got, d, closest = mn.popup_research(refs, img, places, s)
    assert got is None and closest == "Raining Gold" and d > mn.MAX_DISTANCE
    blank = np.zeros_like(img)
    blank[:] = (41, 82, 132)  # the 9.1.3a popup's panel, no icon
    assert mn.popup_research(REFS, blank, places, s)[0] is None


def test_a_few_specks_on_an_empty_panel_are_no_research():
    """Review 2026-10-28: Mana Heroes' sparse reference is the closest to an almost empty
    window; in a tree without Damage Specialization every other name is 2.5 x as far, so
    the loose match also needs the window to be far from no icon at all. The owner's 9.1.3a
    band with the icon painted out by the panel's rows, and the review's trial 56 specks."""
    img = _rgb("meteorite-popup-band-all-attributes-913a").copy()  # 1920x1009: 1 px a px
    img[:] = img[:, :5].mean(axis=1, keepdims=True).astype(np.uint8)  # the panel, no icon
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    for x, y, r, rgb in ((32, 49, 5, (255, 200, 60)), (23, 31, 8, (255, 200, 60))) + (
        (94, 70, 7, (255, 255, 255)),
    ):
        img[np.hypot(yy - y, xx - x) <= r] = rgb
    places, s = _band_places(img)
    for tree in ("3", "7", "12", "B"):
        names = frozenset(research_data.meteorite_names_of(tree))
        assert "Mana Heroes" in names and "Damage Specialization" not in names
        got, d, closest = mn.popup_research(REFS, img, places, s, names)
        assert got is None and closest == "Mana Heroes" and d < mn.POPUP_LOOSE_DISTANCE
    # the real Raining Gold popup is still named in its tree
    gold = _rgb("meteorite-popup-band-raining-gold-913a")
    places, s = _band_places(gold)
    six = frozenset(research_data.meteorite_names_of("6"))
    assert mn.popup_research(REFS, gold, places, s, six)[0] == "Raining Gold"


def test_references_cover_every_research_and_are_distinct():
    assert set(REFS.refs) == set(research_data.meteorite_names())
    names = sorted(REFS.refs)
    mask = mn.block_mask()
    for a in names:
        near = min(float(np.abs(REFS.refs[a] - REFS.refs[b])[mask].mean()) for b in names if b != a)
        assert near > 6, a
    blank = np.zeros((161, 141, 3), np.uint8)
    blank[:] = (41, 170, 247)  # a glowing disc with no icon
    got, d1, *_ = REFS.classify(mn.icon_integral(blank), 70, 70, 1.0)
    assert got is None and d1 > mn.MAX_DISTANCE


def test_the_references_were_built_with_the_readers_settings():
    with open(mn.REFS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    assert raw["grid"] == mn.ICON_GRID
    assert raw["icon_half"] == mn.ICON_HALF
    assert raw["bg_blue_minus_red"] == mn.BG_BLUE_MINUS_RED
    assert raw["bg_blue_min"] == mn.BG_BLUE_MIN
    assert all(len(v) == mn.ICON_GRID * mn.ICON_GRID * 4 for v in raw["refs"].values())


# -- a whole tree ----------------------------------------------------------------------------
BACKGROUND = (30, 70, 140)  # RGB, the tab's dark blue
LINE = (41, 255, 255)  # the lines' core colour
START = (150, 450)
CHAINS = [
    [(350, 200), (560, 200), (770, 200), (980, 200)],
    [(350, 450), (560, 450), (770, 450), (980, 450)],
    [(350, 700), (560, 700), (770, 700), (980, 700)],
]
CROP_CENTRE = 70


def _segment(img, a, b, width=5.0):
    (ax, ay), (bx, by) = a, b
    x0, y0 = min(ax, bx) - 3, min(ay, by) - 3
    yy, xx = np.mgrid[y0 : max(ay, by) + 4, x0 : max(ax, bx) + 4]
    t = ((xx - ax) * (bx - ax) + (yy - ay) * (by - ay)) / float((bx - ax) ** 2 + (by - ay) ** 2)
    t = np.clip(t, 0, 1)
    d = np.hypot(xx - (ax + t * (bx - ax)), yy - (ay + t * (by - ay)))
    img[y0 : y0 + d.shape[0], x0 : x0 + d.shape[1]][d <= width / 2] = LINE


def _paste(img, crop, centre):
    """The crop's disc (r 58) and level label, centred on `centre`."""
    ch, cw = crop.shape[:2]
    yy, xx = np.mgrid[0:ch, 0:cw]
    keep = np.hypot(yy - CROP_CENTRE, xx - CROP_CENTRE) <= 58
    keep |= (xx >= CROP_CENTRE - 30) & (xx < CROP_CENTRE + 31) & (yy >= CROP_CENTRE + 44)
    x0, y0 = centre[0] - CROP_CENTRE, centre[1] - CROP_CENTRE
    view = img[y0 : y0 + ch, x0 : x0 + cw]
    view[keep] = crop[keep]


def _tree(skip_line=None):
    """RGB tree at logical scale; node i: 0 = start, then the chains in order."""
    img = np.zeros((850, 1100, 3), np.uint8)
    img[:] = BACKGROUND
    centres = [START] + [p for chain in CHAINS for p in chain]
    lines = []
    for chain in CHAINS:
        prev = START
        for p in chain:
            lines.append((prev, p))
            prev = p
    for k, (a, b) in enumerate(lines):
        if k != skip_line:
            _segment(img, a, b)
    crops = [_rgb(n) for n in sorted(NODE_CROPS)]
    for i, c in enumerate(centres):
        _paste(img, crops[i % 3], c)
    return img, centres


def _index(nodes, centres, scale=1.0):
    """Node index of each built centre."""
    out = []
    for x, y in centres:
        d = [np.hypot(n.cx - x * scale, n.cy - y * scale) for n in nodes]
        assert min(d) < 3 * max(scale, 1.0)
        out.append(int(np.argmin(d)))
    return out


def _half(img):
    h, w = img.shape[0] // 2 * 2, img.shape[1] // 2 * 2
    return img[:h, :w].reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3)).round().astype(np.uint8)


@pytest.mark.parametrize("scale", [1.0, 0.5])
def test_the_lines_give_the_start_and_each_nodes_parent(scale):
    img, centres = _tree()
    if scale != 1.0:
        img = _half(img)
    tree = mn.scan(img, scale, REFS, _read)
    assert len(tree.nodes) == 13 and len(tree.edges) == 12 and tree.graph is not None
    idx = _index(tree.nodes, centres, scale)
    maxed_crop = sorted(NODE_CROPS).index("meteorite-node-maxed-raining-gold-30")
    assert [tree.nodes[k].maxed for k in idx] == [i % 3 == maxed_crop for i in range(13)]
    start, runs = tree.graph
    assert start == idx[0]
    assert sorted(runs) == sorted([[idx[1 + 4 * c + k] for k in range(4)] for c in range(3)])
    parent = mn.parents(tree.graph)
    assert parent[idx[0]] is None
    for c in range(3):
        prev = idx[0]
        for k in range(4):
            assert parent[idx[1 + 4 * c + k]] == prev
            prev = idx[1 + 4 * c + k]
    order = sorted(NODE_CROPS)
    names = [tree.nodes[k].name for k in idx]
    assert names == [NODE_CROPS[order[i % 3]][2] for i in range(13)]
    if scale == 1.0:
        levels = [tree.nodes[k].level for k in idx]
        assert levels == [NODE_CROPS[order[i % 3]][1] for i in range(13)]


def test_a_missing_line_is_not_taken_for_another_tree():
    img, _ = _tree(skip_line=5)  # the second chain's second line
    tree = mn.scan(img, 1.0)
    assert len(tree.nodes) == 13 and len(tree.edges) == 11
    assert tree.graph is None


def test_assign_gives_each_of_the_trees_names_once():
    """Three nodes side by side, named within a set that holds them: one name each."""
    img = np.zeros((180, 470, 3), np.uint8)
    img[:] = BACKGROUND
    order = sorted(NODE_CROPS)
    for i, name in enumerate(order):
        _paste(img, _rgb(name), (80 + 155 * i, 80))
    nodes = mn.detect_nodes(img, 1.0)
    assert len(nodes) == 3
    names = frozenset(research_data.meteorite_names_of("10"))
    REFS.assign(mn.icon_integral(img), nodes, 1.0, names)
    assert [n.name for n in sorted(nodes, key=lambda n: n.cx)] == [NODE_CROPS[o][2] for o in order]


# -- the tab as the feature reads it ---------------------------------------------------------
class PlacedRefs:
    """Names the built tree's nodes by where they were put (the crops hold three researches
    only): tree 10's start, then its branches. The plain classification leaves one node
    unnamed, as the ratio test does with a look-alike."""

    def __init__(self, centres, unnamed="Mana Heroes"):
        t = research_data.meteorite_tree("10")
        order = [t["start"][0]] + [n for b in t["branches"].values() for n, _, _ in b]
        self.by_centre = dict(zip(centres, order, strict=True))
        self.unnamed = unnamed
        self.calls = []

    def assign(self, integral, nodes, scale=1.0, names=None):
        self.calls.append(names)
        for n in nodes:
            c = min(self.by_centre, key=lambda c: np.hypot(n.cx - c[0], n.cy - c[1]))
            name = self.by_centre[c]
            n.name = None if names is None and name == self.unnamed else name


def test_the_tab_takes_its_names_from_the_layout_and_its_parents_from_the_lines():
    img, centres = _tree()
    refs = PlacedRefs(centres)
    tab = meteorite.analyse(img, 1.0, read=_read, refs=refs)
    ten = frozenset(research_data.meteorite_names_of("10"))
    assert refs.calls == [None, ten]  # named again within the tree's 13 names
    assert tab.names == ten and {n.name for n in tab.nodes} == ten
    assert tab.graph_read
    assert tab.parent("Firestone Effect") is None
    assert tab.parent("Energy Heroes") == "Firestone Effect"
    assert tab.parent("Attribute Armor") == "Raining Gold"
    assert tab.parent("Mana Heroes") == "Firestone Effect"
    assert tab.costs["Tank Specialization"] == 750 and tab.costs["Firestone Effect"] == 900
    # every cost the candidate layouts give (tree 6 has Tank Specialization at 900), and the
    # unlock levels of the layer the lines put a node on
    assert tab.cost_options["Tank Specialization"] == {750, 900}
    assert tab.cost_options["Attribute Armor"] == {800}
    assert tab.layer("Attribute Armor") == 4 and tab.unlock_need("Attribute Armor") == (5, 6)
    assert tab.unlock_need("Firestone Effect") is None  # the start needs nothing
    node = tab.node("tank specialization")  # the game writes "Tank specialization"
    x1, y1 = atlas.METEORITE_TREE_RECT[:2]
    assert tab.point(node) == atlas.Point(
        round(x1 + node.cx), round(y1 + node.cy), atlas.ANCHOR_CENTER
    )


def test_without_the_lines_the_parents_come_from_the_layouts_that_agree():
    img, centres = _tree(skip_line=5)
    tab = meteorite.analyse(img, 1.0, refs=PlacedRefs(centres))
    assert not tab.graph_read
    keys = meteorite.layouts_for(set(research_data.meteorite_names_of("10")))
    assert tab.parents == meteorite.layout_parents(keys)
    assert tab.parent("Attribute Damage") is meteorite.UNKNOWN
    # its layer is not known either: the unlock levels of every layer, and no verdict
    assert tab.layer("Attribute Damage") is None
    assert tab.unlock_need("Attribute Damage") == (5, 7)
    assert tab.unlock_state("Attribute Damage") is None


def test_a_tab_with_names_of_no_known_tree_keeps_the_plain_names():
    """Names that no tree of the data holds together: no layout, no second naming."""
    assert meteorite.layouts_for({"Scroll of Speed", "Tank Specialization"}) == []
    assert meteorite.name_set([]) is None
    assert meteorite.name_set(["3", "7"]) is not None  # one name set laid out two ways
    assert meteorite.name_set(["3", "10"]) is None
