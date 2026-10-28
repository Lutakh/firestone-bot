"""One look at the bag against the old way, on a model of the Chests tab: whatever the bag
holds, in whatever order, the quick visit opens exactly what trying every chest type opens,
and never tries a type or turns the wheel where the old way would not.

The model: the chest types in a packed list (any order), empty slots after the last one up to
whole rows and at least five rows, five rows in view from the scroll offset; the wheel scrolls
by a few rows, clamped at the end; an opened type leaves the list. Reads are exact: a type
with an icon reference by its name, one without as unrecognised, an empty slot as EMPTY; a
colour search finds a type when it is in view.
"""

from __future__ import annotations

import random

import pytest

from firestone_bot.features import open_chests
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas, chest_grid, layouts

E = chest_grid.EMPTY
GIFT, BOX = "Oracle Gift", "Mystery Box"
COLOR = dict(atlas.GEAR_CHESTS + atlas.JEWEL_CHESTS + atlas.CELESTIAL_CHESTS)
COLOR[GIFT] = atlas.ORACLE_GIFT_COLOR
COLOR[BOX] = atlas.MYSTERY_BOX_COLOR
BY_COLOR = {c: n for n, c in COLOR.items()}
TYPES = sorted(COLOR)
NOW_MS = 50_000_000


class ModelBag:
    """The bag open on its Chests tab, as the game draws it."""

    def __init__(self, types, wheel_rows, full):
        self.items = list(types)
        self.offset = 0  # rows scrolled
        self.wheel_rows = wheel_rows
        self.ms = layouts.NEW
        self.dry_run = False
        self.vars = {} if full else {open_chests.FULL_CHECK_KEY: NOW_MS}
        self.tried: list[str] = []
        self.opened: list[str] = []
        self.wheels = 0

    def _slots(self):
        total = max(15, -(-len(self.items) // 3) * 3)
        return self.items + [E] * (total - len(self.items))

    def view(self):
        return self._slots()[self.offset * 3 : self.offset * 3 + 15]

    def read(self):
        return [s if s == E or chest_grid.known(s) else None for s in self.view()]

    def try_open(self, name):
        self.tried.append(name)
        if name in self.view():
            self.opened.append(name)
            self.items.remove(name)
            self.offset = min(self.offset, len(self._slots()) // 3 - 5)

    # the Game calls the visit makes
    def found(self, p, variation=None):
        if p is self.ms.bag_close_x:
            return True
        return BY_COLOR[p.color] in self.view()

    def wheel(self, notches, interval_ms=200):
        self.wheels += 1
        self.offset = min(len(self._slots()) // 3 - 5, self.offset + self.wheel_rows)

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def toast(self, title, text, seconds):
        pass

    def status(self, text):
        pass

    def tap(self, p, settle_ms=1500, expect=None):
        pass

    def save_diagnostic(self, name):
        pass


def _gift(name):
    def opener(g, scroll=True):
        if scroll:
            g.wheel(-5)
        g.try_open(name)

    return opener


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setattr(open_chests, "_now_ms", lambda: NOW_MS)
    monkeypatch.setattr(open_chests, "_open_bag_chests_tab", lambda g: None)
    monkeypatch.setattr(chest_grid, "read_slots", lambda g: g.read())
    monkeypatch.setattr(open_chests, "open_chest_type", lambda g, c, v, name: g.try_open(name))
    monkeypatch.setattr(open_chests, "oracles_gift", _gift(GIFT))
    monkeypatch.setattr(open_chests, "mystery_box", _gift(BOX))


def _settings(rng):
    s = Settings()
    for key in ("Chests", "OracleGifts", "MysteryBoxes", "Bless", "BlessingChests"):
        s.set(key, rng.choice("01"))
    s.set("GearChestExclude", rng.choice(list(atlas.GEAR_CHEST_START)))
    s.set("JewelChestExclude", rng.choice(list(atlas.JEWEL_CHEST_START)))
    s.set("CelestialChestExclude", rng.choice(list(atlas.CELESTIAL_CHEST_START)))
    return s


@pytest.mark.parametrize("wheel_rows", [1, 2, 99])
def test_the_look_opens_what_trying_every_chest_opens(model, wheel_rows):
    rng = random.Random(wheel_rows)
    for _ in range(300):
        types = rng.sample(TYPES, rng.choice([0, 1, 2, 5, 11, 12, 13, 14, 15, 16, 17, 19, 21]))
        settings = _settings(rng)
        visits = {}
        for full in (True, False):
            bag = ModelBag(types, wheel_rows, full)
            bag.settings = settings
            open_chests.open_bag(bag)
            visits[full] = bag
        old, quick = visits[True], visits[False]
        case = (types, settings.values)
        assert quick.opened == old.opened, case
        assert set(quick.tried) <= set(old.tried), case
        assert quick.wheels <= old.wheels, case
