"""Counters of the spend screens read as numbers; the arcane crystal counts a hit only when
the pickaxe counter drops."""

import os
from pathlib import Path

import numpy as np
import pytest

from firestone_bot.features import guild, token_counter
from firestone_bot.game import Game, prune_diagnostics
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas
from firestone_bot.vision.digits import DigitReader

FIX = Path(__file__).parent / "fixtures"


class Reader:
    def __init__(self):
        self.reader = DigitReader()

    def digit_reader(self):
        return self.reader


@pytest.mark.parametrize(
    "name, value",
    [
        ("chaos-free-10", 10),
        ("chaos-free-9", 9),
        ("chaos-free-0", 0),
        ("crystal-pickaxes-52", 52),
    ],
)
def test_counters_read_on_real_captures(name, value):
    img = np.load(FIX / f"{name}.npy")
    assert token_counter.read_image(Reader(), img) == value
    # a dialog dimming the screen never passes for a lower number
    dimmed = (img.astype(np.float32) * 0.5).astype(np.uint8)
    assert token_counter.read_image(Reader(), dimmed) is None


def test_a_digit_cut_by_the_rect_is_unreadable_not_a_wrong_number():
    """The free counter rect shifted 40 px (another window shape): the digit reader alone
    reads the "0" of "10" and says 0, which would stop the day's hits."""
    img = np.load(FIX / "chaos-free-10-cut.npy")
    assert DigitReader().read(img) == 0
    assert token_counter.read_image(Reader(), img) is None


class Clock:
    def __init__(self, reads):
        self.reads = list(reads)

    def sleep(self, ms):
        pass


def test_wait_drop_needs_the_same_lower_value_twice(monkeypatch):
    def run(reads, before=10, timeout_ms=3000):
        g = Clock(reads)
        monkeypatch.setattr(
            token_counter, "read", lambda game, rect: game.reads.pop(0) if game.reads else before
        )
        return token_counter.wait_drop(g, (0, 0, 1, 1), before, timeout_ms)

    assert run([10, 9, 9]) == 9
    assert run([None, 9, 9]) == 9
    assert run([9, 10, 10]) is None  # one low read is not enough
    assert run([10] * 40) is None


# --- arcane crystal ---------------------------------------------------------------------


class FakeCrystal:
    def __init__(self, tmp_path, pickaxes, taken, count=13, readable=True):
        self.settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        self.settings.set("MaxCrystals", 15)
        self.settings.set("CrystalCountDaily", count)
        self.pickaxes = pickaxes
        self.taken = list(taken)
        self.readable = readable
        self.taps = 0
        self.vars = {}
        self.lines = []
        self.captures = []
        self.region_changes = []

    def found(self, probe):
        assert probe is atlas.GUILD_CRYSTAL_HIT_READY
        return True

    def tap(self, point, settle_ms=1500, expect=None):
        if point is atlas.GUILD_CRYSTAL:
            return
        assert point is atlas.GUILD_CRYSTAL_HIT
        self.taps += 1
        if self.taken.pop(0) if self.taken else True:
            self.pickaxes -= 1

    def region_image(self, rect, anchor=None):
        return np.random.randint(0, 255, (30, 100, 3), dtype=np.uint8)  # always "changed"

    def wait_region_change(self, rect, before, timeout_ms=15000, anchor=None):
        self.region_changes.append((rect, anchor))
        return True

    def move_to(self, point):
        pass

    def sleep(self, ms):
        pass

    def heartbeat(self, *a, **kw):
        pass

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)


@pytest.fixture
def crystal(monkeypatch, tmp_path):
    def make(**kw):
        g = FakeCrystal(tmp_path, **kw)
        monkeypatch.setattr(
            token_counter, "read", lambda game, rect: game.pickaxes if game.readable else None
        )
        monkeypatch.setattr(guild, "big_close", lambda game: None)
        monkeypatch.setattr(guild.multiplier, "ensure_single", lambda game, screen: True)
        return g

    return make


def _crystals(g):
    return int(g.settings.get("CrystalCountDaily"))


def test_crystal_counts_only_hits_that_took_a_pickaxe(crystal):
    """A redraw of the old counter area (sky, box edge) counted an ignored click: 15
    counted, 14 made (owner, 2026-09-24). The random region image stands for that redraw."""
    g = crystal(pickaxes=40, taken=[True, False, True])
    guild.hit_crystal(g)
    assert g.taps == 3
    assert _crystals(g) == 15
    assert g.pickaxes == 38
    assert any("did not go down, not counted" in s for s in g.lines)


def test_crystal_leaves_after_repeated_ignored_clicks(crystal):
    g = crystal(pickaxes=40, taken=[False, False, False])
    guild.hit_crystal(g)
    assert g.taps == 3
    assert _crystals(g) == 13
    assert g.captures == ["crystal-hit-not-taken.png"]


def test_crystal_without_pickaxes_is_not_clicked(crystal):
    g = crystal(pickaxes=0, taken=[])
    guild.hit_crystal(g)
    assert g.taps == 0


def test_crystal_counter_unreadable_falls_back_to_the_digits_pixels(crystal):
    g = crystal(pickaxes=40, taken=[True, True], readable=False)
    guild.hit_crystal(g)
    assert _crystals(g) == 15
    assert g.region_changes == [(atlas.GUILD_PICKAXE_DIGITS, atlas.ANCHOR_TOP_RIGHT)] * 2
    assert g.captures == ["crystal-counter-unread.png"]  # once per visit


# --- diagnostics and screens --------------------------------------------------------------


def test_prune_keeps_the_newest_of_each_kind(tmp_path):
    """Named by time of day and pruned by name, a capture taken before 23:57 was deleted as
    soon as it was written."""
    old = 1_700_000_000
    for i in range(40):
        p = tmp_path / f"2359{i:02d}-town-open.png"
        p.write_bytes(b"x")
        os.utime(p, (old + i, old + i))
    rare = tmp_path / "20260924-101500-research-no-node.png"
    rare.write_bytes(b"x")
    os.utime(rare, (old - 100, old - 100))  # older than all the town captures
    new = tmp_path / "20260924-120000-chaos-hit-not-taken.png"
    new.write_bytes(b"x")
    os.utime(new, (old - 200, old - 200))  # even a clock gone back keeps the new file
    prune_diagnostics(str(tmp_path), spare=str(new))
    left = sorted(os.listdir(tmp_path))
    assert rare.name in left and new.name in left
    assert sum(name.endswith("town-open.png") for name in left) == 3
    assert "235939-town-open.png" in left  # the newest ones


class TownFake:
    TOWN_GONE_MS = 5000
    BUILDING_X_MS = 2000

    def __init__(self, town_stays, arrow_back=False, x_shown=True):
        self.town_stays = town_stays
        self.arrow_back = arrow_back  # the arrow missed one frame on the town itself
        self.x_shown = x_shown
        self.settled = False

    def wait_gone(self, probe, timeout_ms):
        assert probe is atlas.TOWN_OPEN
        return not self.town_stays

    def wait_still(self):
        self.settled = True

    def found(self, probe):
        if probe is atlas.TOWN_OPEN:
            return self.arrow_back
        return True  # the dialog X: the town shows one too

    def wait_for(self, probe, timeout_ms):
        assert self.settled, "the building is read before it settled"
        return self.x_shown


def test_a_building_is_reached_only_once_the_town_is_gone():
    reached = Game._screen_reached
    assert reached(TownFake(town_stays=True), atlas.DIALOG_CLOSE_X, True) is False
    assert reached(TownFake(town_stays=False), atlas.DIALOG_CLOSE_X, True) is True
    assert reached(TownFake(False, arrow_back=True), atlas.DIALOG_CLOSE_X, True) is False
    assert reached(TownFake(False, x_shown=False), atlas.DIALOG_CLOSE_X, True) is False
    # a screen with its own probe, or not opened from the town, is not concerned
    assert reached(TownFake(town_stays=True), atlas.TAVERN_CLOSE_X, True) is True
    assert reached(TownFake(town_stays=True), atlas.DIALOG_CLOSE_X, False) is True
