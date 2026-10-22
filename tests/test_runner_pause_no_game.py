"""A pause that ends in "new cycle" while the game is closed (a scheduled restart) must not
crash the run: the next cycle launches the game (owner, 2026-10-22)."""

from __future__ import annotations

from types import SimpleNamespace

from firestone_bot import runner
from firestone_bot.features import big_close
from firestone_bot.platform.types import GameWindowNotFound


def test_no_game_window_after_a_pause_is_not_a_crash(monkeypatch):
    lines = []
    g = SimpleNamespace(focus=lambda: None, status=lines.append)

    def closed(game):
        raise GameWindowNotFound("Firestone process not running")

    monkeypatch.setattr(big_close, "big_close", closed)
    runner.Runner._back_to_main_screen(SimpleNamespace(g=g))
    assert lines == ["No game window after the pause; the next cycle starts the game"]
