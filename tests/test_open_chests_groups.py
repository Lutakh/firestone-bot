"""Which chests each exclusion setting opens: every rarity below the kept one, none above.

"Nebula and Higher" and "Cosmic and Higher" jumped to Galaxy in the AHK ladder and opened every
celestial chest (a user's report, 2026-09-29).
"""

from __future__ import annotations

import pytest

from firestone_bot.features import open_chests
from firestone_bot.gui.catalog import CELESTIAL_CHOICES, GEAR_CHOICES, JEWEL_CHOICES
from firestone_bot.vision import atlas


class FakeGame:
    def toast(self, title: str, text: str, seconds: float) -> None:
        pass


def opened(monkeypatch, group, start) -> list[str]:
    names: list[str] = []
    monkeypatch.setattr(
        open_chests, "open_chest_type", lambda g, color, variation, name: names.append(name)
    )
    open_chests._open_group(FakeGame(), group, start)
    return names


@pytest.mark.parametrize(
    "setting, expected",
    [
        ("Exclude All", []),
        ("Don't Exclude Any", ["Galaxy", "Cosmic", "Nebula", "Solar", "Lunar", "Comet"]),
        ("Solar and Higher", ["Lunar", "Comet"]),
        ("Nebula and Higher", ["Solar", "Lunar", "Comet"]),
        ("Cosmic and Higher", ["Nebula", "Solar", "Lunar", "Comet"]),
        ("Galaxy", ["Cosmic", "Nebula", "Solar", "Lunar", "Comet"]),
    ],
)
def test_celestial_settings_keep_the_named_rarity_and_higher(monkeypatch, setting, expected):
    start = atlas.CELESTIAL_CHEST_START[setting]
    assert opened(monkeypatch, atlas.CELESTIAL_CHESTS, start) == expected


@pytest.mark.parametrize(
    "setting, expected",
    [
        ("Titan", ["Mythic", "Legendary", "Epic", "Rare", "Uncommon", "Common"]),
        ("Mythic and Higher", ["Legendary", "Epic", "Rare", "Uncommon", "Common"]),
        ("Legendary and Higher", ["Epic", "Rare", "Uncommon", "Common"]),
        ("Epic and Higher", ["Rare", "Uncommon", "Common"]),
    ],
)
def test_gear_settings_keep_the_named_rarity_and_higher(monkeypatch, setting, expected):
    start = atlas.GEAR_CHEST_START[setting]
    assert opened(monkeypatch, atlas.GEAR_CHESTS, start) == expected


@pytest.mark.parametrize(
    "setting, expected",
    [
        ("Platinum", ["Emerald", "Opal", "Diamond", "Golden", "Iron", "Wooden"]),
        ("Emerald and Higher", ["Opal", "Diamond", "Golden", "Iron", "Wooden"]),
        ("Opal and Higher", ["Diamond", "Golden", "Iron", "Wooden"]),
        ("Diamond and Higher", ["Golden", "Iron", "Wooden"]),
    ],
)
def test_jewel_settings_keep_the_named_rarity_and_higher(monkeypatch, setting, expected):
    start = atlas.JEWEL_CHEST_START[setting]
    assert opened(monkeypatch, atlas.JEWEL_CHESTS, start) == expected


def test_every_gui_choice_has_a_start():
    for choices, starts in (
        (CELESTIAL_CHOICES, atlas.CELESTIAL_CHEST_START),
        (GEAR_CHOICES, atlas.GEAR_CHEST_START),
        (JEWEL_CHOICES, atlas.JEWEL_CHEST_START),
    ):
        assert set(choices) == set(starts)
