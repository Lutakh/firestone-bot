"""The map-opening dropdown must select the actual path used by the runner."""

from types import SimpleNamespace

import pytest

from firestone_bot.features.go_map import _hotkey, _use_icon
from firestone_bot.settings import Settings


@pytest.mark.parametrize(
    "mode,style,icon",
    [
        ("hotkey", "new", False),
        ("hotkey", "classic", False),
        ("icon", "new", True),
        ("auto", "new", True),
        ("auto", "classic", False),
    ],
)
def test_map_opening_choice_matches_dropdown_values(mode, style, icon):
    settings = Settings(path="unused-settings.ini", loaded=True)
    settings.set("MapOpen", mode)
    settings.set("MapHotkey", "P")
    game = SimpleNamespace(settings=settings, style=style)
    assert _use_icon(game) is icon
    assert _hotkey(game) == "p"
