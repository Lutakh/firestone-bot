"""One look at the bag (a user's suggestion, 2026-10-28): the visible slots of the chest grid
are read once, a chest with an icon reference is only tried when a slot holds it, the wheel
is not used when the whole list is in view, and anything doubtful goes the old way."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from firestone_bot import runner
from firestone_bot.features import open_chests, oracles_gift
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas, chest_grid, layouts

E = chest_grid.EMPTY
FIXTURES = Path(__file__).parent / "fixtures"
# The chest grid as GridImage captures it (BGR), cut from real captures:
# the owner's Windows client 1920x1009, new style, game before 9.1.3a (2026-09-05), scaled to
# a third (a 640x336 client); the panel's X was found at logical (1888, 92)
NEW_GRID = np.load(FIXTURES / "bag-grid-new-1920x1009-third.npy")
# Qualitas's video (Steam, classic style, game 9.1.3a, 2026-10-22; 854x480 of a 1920x1080
# screen, client 1920x1009 at y 23) at 14.4 s, scaled to 3/4; the panel's X at (1889, 249)
CLASSIC_GRID = np.load(FIXTURES / "bag-grid-classic-913a-video.npy")
OWNERS_BAG = [
    "Common",
    "Uncommon",
    "Rare",
    "Epic",
    "Legendary",
    "Mythic",
    "Wooden",
    "Iron",
    "Golden",
    "Diamond",
    "Opal",
    "Emerald",
    E,
    E,
    E,
]


class GridGame:
    """What chest_grid reads: the panel's X (the rows are placed from it) and the grid."""

    def __init__(self, img, style, x, rect):
        self.img, self.ms, self.x, self.rect = img, layouts.BY_NAME[style], x, rect

    def search(self, p, variation=None):
        assert p is self.ms.bag_close_x
        return SimpleNamespace(x=self.x[0], y=self.x[1])

    def region_image(self, rect, anchor=None):
        assert rect == self.rect  # the region the fixture was cut from
        return self.img


def test_the_owners_new_style_bag_reads_twelve_chests_then_empty_slots():
    g = GridGame(NEW_GRID, "new", (1888, 92), (1539, 160, 1901, 757))
    slots = chest_grid.read_slots(g)
    assert slots == OWNERS_BAG
    assert open_chests.BagLook(slots).end_in_view


def test_a_classic_bag_on_913a_reads_its_mystery_box_as_unrecognised():
    g = GridGame(CLASSIC_GRID, "classic", (1889, 249), (1539, 317, 1901, 914))
    slots = chest_grid.read_slots(g)
    assert slots == [None] + [E] * 14  # the box has no reference: never "empty"
    look = open_chests.BagLook(slots)
    assert look.end_in_view and look.summary() == "1 unrecognised, 14 empty slots"


@pytest.mark.parametrize(
    "slots, end",
    [
        ([E] * 15, True),  # an empty bag
        (["Opal", "Emerald"] + [E] * 13, True),
        ([None] + [E] * 14, True),
        (["Opal"] * 15, False),  # a full view: more may be below
        (["Opal", E, "Emerald"] + [E] * 12, False),  # not packed: something is off
        (["Opal"] + [E] * 13 + [None], False),  # the last slot is not empty
        ([None] * 15, False),  # nothing read
    ],
)
def test_the_list_ends_in_view_only_after_a_packed_run_of_empty_slots(slots, end):
    assert open_chests.BagLook(slots).end_in_view is end


# -- the bag visit ------------------------------------------------------------------------
NOW_MS = 50_000_000  # open_chests._now_ms() in these tests


class FakeBag:
    """The bag open on its Chests tab. `reads`: successive results of chest_grid.read_slots
    (the last one repeats); `colours`: the chest colours a search of the grid finds."""

    def __init__(self, reads, colours=(), dry_run=False, x_found=True):
        self.reads = [list(r) for r in reads]
        self.colours = set(colours)
        self.dry_run = dry_run
        self.x_found = x_found
        self.ms = layouts.NEW
        self.vars = {open_chests.FULL_CHECK_KEY: NOW_MS}  # a full check just happened
        self.settings = Settings()
        for key, value in {
            "Chests": "1",
            "GearChestExclude": "Don't Exclude Any",
            "JewelChestExclude": "Opal and Higher",
            "CelestialChestExclude": "Don't Exclude Any",
            "Bless": "1",
            "BlessingChests": "1",
            "OracleGifts": "1",
            "MysteryBoxes": "1",
        }.items():
            self.settings.set(key, value)
        self.log: list[tuple] = []
        self.statuses: list[str] = []
        self.n_reads = 0

    def read(self):
        self.n_reads += 1
        return self.reads.pop(0) if len(self.reads) > 1 else list(self.reads[0])

    def found(self, p, variation=None):
        if p is self.ms.bag_close_x:
            return self.x_found and self.bag_open()
        self.log.append(("search", p.name))
        return p.color in self.colours

    def bag_open(self):
        """Opened (the patched _open_bag_chests_tab) and not closed since: the X shows."""
        close = ("tap", (self.ms.bag_close.x, self.ms.bag_close.y))
        opened = [i for i, e in enumerate(self.log) if e == ("bag",)]
        return bool(opened) and close not in self.log[opened[-1] :]

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def toast(self, title, text, seconds):
        self.log.append(("toast", text))

    def status(self, text):
        self.statuses.append(text)

    def wheel(self, notches, interval_ms=200):
        self.log.append(("wheel", notches))

    def tap(self, p, settle_ms=1500, expect=None):
        self.log.append(("tap", (p.x, p.y)))

    def save_diagnostic(self, name):
        self.log.append(("capture", name))

    def opened(self):
        return [e[1] for e in self.log if e[0] == "open"]

    def searched(self):
        return [e[1] for e in self.log if e[0] == "search"]


@pytest.fixture
def bag(monkeypatch):
    """A FakeBag maker with the feature's game actions recorded instead of played."""
    monkeypatch.setattr(open_chests, "_now_ms", lambda: NOW_MS)
    monkeypatch.setattr(open_chests, "_open_bag_chests_tab", lambda g: g.log.append(("bag",)))
    monkeypatch.setattr(chest_grid, "read_slots", lambda g: g.read())
    monkeypatch.setattr(
        open_chests,
        "open_chest_type",
        lambda g, color, variation, name: g.log.append(("open", name)),
    )
    monkeypatch.setattr(
        open_chests, "oracles_gift", lambda g, scroll=True: g.log.append(("gift", scroll))
    )
    monkeypatch.setattr(
        open_chests, "mystery_box", lambda g, scroll=True: g.log.append(("box", scroll))
    )
    return FakeBag


ALL_TYPES = [n for n, _ in atlas.GEAR_CHESTS] + ["Diamond", "Golden", "Iron", "Wooden"]
ALL_TYPES += [n for n, _ in atlas.CELESTIAL_CHESTS]
COLOUR_ONLY = ["chest_08BAC6", "gift_FFD800", "gift_F78BF1"] + [
    f"chest_{c:06X}" for n, c in atlas.CELESTIAL_CHESTS if not chest_grid.known(n)
]


def _closes(g):
    return sum(1 for e in g.log if e == ("tap", (g.ms.bag_close.x, g.ms.bag_close.y)))


def test_the_owners_usual_bag_is_read_once_and_nothing_else_is_tried(bag):
    g = bag([["Emerald", "Opal"] + [E] * 13])  # kept chests only ("Opal and Higher")
    open_chests.open_bag(g)
    assert g.opened() == [] and g.n_reads == 2  # one look: two reads that agree
    assert g.searched() == COLOUR_ONLY  # Titan, gifts, boxes, Galaxy..Solar by their colour
    assert not [e for e in g.log if e[0] in ("toast", "wheel", "gift", "box")]
    assert _closes(g) == 1
    assert g.statuses == ["Open Chests: the bag shows Emerald, Opal, 13 empty slots"]


def test_a_chest_in_the_bag_is_opened_and_the_bag_read_again(bag):
    g = bag([["Common", "Emerald", "Opal"] + [E] * 12] * 2 + [["Emerald", "Opal"] + [E] * 13])
    open_chests.open_bag(g)
    assert g.opened() == ["Common"]
    assert ("toast", "Opening Common Chests") in g.log
    assert g.n_reads == 4  # a second look after the opening
    assert g.statuses[-1] == "Open Chests: the bag shows Emerald, Opal, 13 empty slots"


def test_a_chest_without_a_reference_is_found_by_its_colour(bag):
    nebula = dict(atlas.CELESTIAL_CHESTS)["Nebula"]
    g = bag([[None, "Opal"] + [E] * 13], colours={nebula})
    open_chests.open_bag(g)
    assert g.opened() == ["Nebula"]
    assert ("toast", "Opening Nebula Chests") in g.log


def test_gifts_in_view_are_opened_without_the_wheel(bag):
    g = bag([[None] + [E] * 14], colours={atlas.MYSTERY_BOX_COLOR})
    open_chests.open_bag(g)
    assert ("box", False) in g.log and ("toast", "Opening Mystery Boxes") in g.log
    assert ("gift", False) not in g.log  # no Oracle's gift colour in the grid
    assert not [e for e in g.log if e[0] == "wheel"]


def test_a_full_view_keeps_the_wheel_for_the_end_of_the_list(bag):
    g = bag([["Opal"] * 15])  # no empty slot: more chests may be below
    open_chests.open_bag(g)
    assert ("gift", True) in g.log and ("box", True) in g.log
    assert ("wheel", -5) in g.log  # before the celestial chests
    assert g.opened() == []  # the reads (here unchanged) name no chest of the plan


def test_reads_that_disagree_fall_back_to_trying_every_chest(bag):
    moving = [[E] * 15, ["Opal"] + [E] * 14, ["Opal", "Opal"] + [E] * 13, [E] * 15]
    g = bag(moving)
    open_chests.open_bag(g)
    assert g.n_reads == open_chests.LOOK_READS
    assert g.opened() == ALL_TYPES  # the old way, in the AHK order
    assert ("gift", True) in g.log and ("box", True) in g.log and ("wheel", -5) in g.log
    assert ("capture", "bag-look.png") in g.log
    assert "Open Chests: the bag could not be read, every chest is tried" in g.statuses
    g.log.clear()
    g.reads = [list(r) for r in moving]
    open_chests.open_bag(g)
    assert g.opened() == ALL_TYPES
    assert ("capture", "bag-look.png") not in g.log  # one capture a run


def test_without_the_bags_x_every_chest_is_tried(bag):
    g = bag([[E] * 15], x_found=False)
    open_chests.open_bag(g)
    assert g.n_reads == 0 and g.opened() == ALL_TYPES


def test_the_pointer_leaves_the_bags_x_before_it_is_read(bag):
    """After an opening the pointer rests on the bag's X (close_chest_dialog): the look parks
    it before it reads the X, as the chest searches did."""
    g = bag([[E] * 15])
    order = []

    def found(p, variation=None):
        if p is g.ms.bag_close_x:
            order.append("x")
        return FakeBag.found(g, p, variation)

    g.move_to, g.found = order.append, found
    g.log.append(("bag",))  # the bag is open
    assert open_chests.take_look(g) is not None
    assert order == [atlas.NS_MODE_PARK, "x"]


def test_each_run_starts_with_a_full_check():
    """Game.vars outlives a Stop: the runner drops the last full check when a run starts."""
    g = SimpleNamespace(front_guard=None, vars={open_chests.FULL_CHECK_KEY: NOW_MS})
    r = runner.Runner.__new__(runner.Runner)
    r.g, r.settings = g, Settings()
    r._cycle = lambda: False
    r.main_script()
    assert open_chests.FULL_CHECK_KEY not in g.vars


def test_the_first_visit_then_one_an_hour_try_every_chest(bag, monkeypatch):
    now = [NOW_MS]
    monkeypatch.setattr(open_chests, "_now_ms", lambda: now[0])
    g = bag([[E] * 15])
    g.vars.clear()  # the first visit of a run
    open_chests.open_bag(g)
    assert g.opened() == ALL_TYPES and g.n_reads == 0
    assert g.vars[open_chests.FULL_CHECK_KEY] == now[0]
    g.log.clear()
    now[0] += open_chests.FULL_CHECK_MS - 1
    open_chests.open_bag(g)
    assert g.opened() == [] and g.statuses[-1] == "Open Chests: the bag shows 15 empty slots"
    now[0] += 1
    open_chests.open_bag(g)
    assert g.opened() == ALL_TYPES


def test_a_full_check_counts_once_it_saw_the_bag(bag):
    """A first visit whose bag never opened (a pop-up took the click) tries every chest on
    whatever is on screen: the full check stays due for the next visit."""
    g = bag([[E] * 15], x_found=False)
    g.vars.clear()
    open_chests.open_bag(g)
    assert g.opened() == ALL_TYPES and open_chests.FULL_CHECK_KEY not in g.vars
    g.x_found = True
    open_chests.open_bag(g)
    assert g.vars[open_chests.FULL_CHECK_KEY] == NOW_MS


def test_a_dry_run_tries_every_chest(bag):
    g = bag([[E] * 15], dry_run=True)
    g.vars.clear()
    open_chests.open_bag(g)
    assert g.opened() == ALL_TYPES and g.n_reads == 0
    assert open_chests.FULL_CHECK_KEY not in g.vars


def test_a_gift_in_view_is_searched_without_the_wheel():
    class G:
        ms = layouts.NEW

        def __init__(self):
            self.log = []

        def move_to(self, p):
            self.log.append("move")

        def toast(self, title, text, seconds):
            self.log.append("toast")

        def wheel(self, notches, interval_ms=200):
            self.log.append("wheel")

        def search(self, p, variation=None):
            self.log.append(p.name)  # no gift in the grid

    g = G()
    oracles_gift.mystery_box(g, scroll=False)
    assert g.log == ["gift_F78BF1"]
    g.log.clear()
    oracles_gift.mystery_box(g)
    assert g.log == ["move", "toast", "wheel", "gift_F78BF1"]
