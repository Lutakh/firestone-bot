"""Arena of Kings. On a 1920x1080 client: the arena is a centred dialog, so its X is looked
for from the centre (report ANHNX9, Steam, 2026-10-25: edge-anchored, the probe sat 68 px
left of the X and the arena "did not show" at every try). A battle whose claim button never
shows ends the arena instead of tapping on blind."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from firestone_bot.features import arena
from firestone_bot.game import ScreenNotReached
from firestone_bot.platform.window import Rect
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas
from firestone_bot.vision.probes import pixel_search_in
from firestone_bot.vision.viewport import Viewport

# 20261025-195217-arena-miss.png (client 1920x1080), client x 1770..1910, y 70..170; BGR
CROP = np.load(Path(__file__).parent / "fixtures" / "arena-close-x-1920x1080.npy")
ORIGIN = Rect(1770, 70, CROP.shape[1], CROP.shape[0])
VP = Viewport(Rect(0, 0, 1920, 1080))


def _found(probe):
    bgra = np.dstack([CROP, np.full(CROP.shape[:2], 255, np.uint8)])
    rect = VP.probe_rect_screen(probe)
    return pixel_search_in(bgra, ORIGIN, rect, probe.color, probe.variation + VP.variation_boost())


def test_the_arena_x_is_found_at_1920x1080():
    assert _found(atlas.ARENA_CLOSE_X) is not None
    # the edge anchor of 0.3.34 (right, top) looked on the dialog's beige panel
    assert _found(replace(atlas.ARENA_CLOSE_X, anchor=(1.0, 0.0))) is None


def test_every_arena_entry_is_centre_anchored():
    for entry in (
        atlas.ARENA_CLOSE_X,
        atlas.ARENA_REFRESH,
        atlas.ARENA_BUY_MORE,
        atlas.ARENA_FIGHT,
        atlas.ARENA_BATTLE_DONE,
        atlas.ARENA_BATTLE_CLAIM,
    ):
        assert entry.anchor == atlas.ANCHOR_CENTER


class Battle:
    """arena_battle's view of the game: the claim button shows after `done_ms`."""

    def __init__(self, cap, done_ms=None, fast=True):
        self.settings = Settings()
        self.settings.set("SafetyCap", cap)
        self.done_ms, self._fast = done_ms, fast
        self.ms = 0
        self.taps, self.lines, self.captures = [], [], []

    def found(self, probe):
        assert probe is atlas.ARENA_BATTLE_DONE
        return self.done_ms is not None and self.ms >= self.done_ms

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append(p)

    def fast(self):
        return self._fast

    def poll_ms(self):
        return 250

    def sleep(self, ms):
        self.ms += ms

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)


def test_a_battle_is_claimed_when_its_button_shows():
    g = Battle("0", done_ms=30_000)
    assert arena.arena_battle(g) is True
    assert g.taps == [atlas.ARENA_BATTLE_CLAIM] and g.captures == []


@pytest.mark.parametrize("cap, limit_s", [("0", 180), ("3", 60), ("20", 180)])
def test_a_claim_button_that_never_shows_ends_the_arena(cap, limit_s):
    """SafetyCap 0 waited forever (AHK); a cap returned and the battle loop tapped on blind."""
    for fast in (True, False):
        g = Battle(cap, fast=fast)
        with pytest.raises(ScreenNotReached):
            arena.arena_battle(g)
        assert g.ms == limit_s * 1000 and g.taps == []
        assert g.captures == ["arena-battle-miss.png"]
        assert g.lines == [f"ArenaBattle: no claim button after {limit_s} s, arena left"]
