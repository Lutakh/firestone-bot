"""Runtime display follows the actual process age and the runner's restart clock."""

from types import SimpleNamespace

import pytest

from firestone_bot import app as app_mod
from firestone_bot import runner as runner_mod
from firestone_bot.platform import process
from firestone_bot.settings import Settings


@pytest.fixture
def application(monkeypatch, tmp_path):
    app = app_mod.App.__new__(app_mod.App)
    app.settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    app.settings.set("RestartGame", "1")
    app.settings.set("RestartGameTime", "6")
    app.settings.set("RestartGameTest", "0")
    app.runner = None
    monkeypatch.setattr(app_mod.time, "monotonic", lambda: 100_000.0)
    monkeypatch.setattr(process, "find_game_process", lambda: object())
    return app


def _running_bot(app, *, interval_hours=6, elapsed_s=60):
    runner = runner_mod.Runner.__new__(runner_mod.Runner)
    runner.thread = SimpleNamespace(is_alive=lambda: True)
    runner._restart_ms = interval_hours * 3_600_000
    runner._last_restart = runner_mod._ms() - elapsed_s * 1000
    app.runner = runner
    return runner


def test_game_started_before_bot_uses_process_age(application, monkeypatch):
    runner = _running_bot(application, elapsed_s=60)
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: 20 * 3600)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["game_uptime_s"] == snapshot["restart_elapsed_s"] == 20 * 3600
    assert snapshot["restart_interval_s"] == 6 * 3600
    assert snapshot["restart_source"] == "game"
    assert snapshot["game_running"] is True
    assert snapshot["observed_at"] == 100_000.0
    assert runner._due(SimpleNamespace(status=lambda _: None))


def test_just_started_game_keeps_a_real_zero_age(application, monkeypatch):
    _running_bot(application, elapsed_s=7 * 3600)
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: 0.0)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["game_uptime_s"] == snapshot["restart_elapsed_s"] == 0.0
    assert snapshot["restart_source"] == "game"


def test_active_interval_matches_cached_runner_then_stopped_uses_settings(application, monkeypatch):
    runner = _running_bot(application, interval_hours=6)
    application.settings.set("RestartGameTime", "2")
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: 3 * 3600)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["restart_interval_s"] == 6 * 3600
    assert snapshot["restart_elapsed_s"] < snapshot["restart_interval_s"]
    assert not runner._due(SimpleNamespace(status=lambda _: None))
    runner.thread.is_alive = lambda: False
    assert application.game_runtime_snapshot()["restart_interval_s"] == 2 * 3600


def test_unknown_game_age_uses_actual_bot_fallback_without_inventing_uptime(
    application, monkeypatch
):
    runner = _running_bot(application, elapsed_s=7 * 3600)
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: None)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["game_uptime_s"] is None
    assert snapshot["game_running"] is True
    assert snapshot["restart_source"] == "bot"
    assert snapshot["restart_elapsed_s"] == 7 * 3600
    assert runner._due(SimpleNamespace(status=lambda _: None))
    runner._last_restart = runner_mod._ms() - 45_000
    assert application.game_runtime_snapshot()["restart_elapsed_s"] == 45
    assert not runner._due(SimpleNamespace(status=lambda _: None))


@pytest.mark.parametrize("elapsed_ms, due", [(21_599_999, False), (21_600_000, True)])
def test_fallback_snapshot_matches_restart_boundary(application, monkeypatch, elapsed_ms, due):
    runner = _running_bot(application)
    runner._last_restart = runner_mod._ms() - elapsed_ms
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: None)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["restart_elapsed_s"] == elapsed_ms / 1000
    assert (snapshot["restart_elapsed_s"] >= snapshot["restart_interval_s"]) is due
    assert runner._due(SimpleNamespace(status=lambda _: None)) is due


@pytest.mark.parametrize("has_runner", [False, True])
def test_idle_unknown_age_does_not_reuse_old_bot_clock(application, monkeypatch, has_runner):
    if has_runner:
        _running_bot(application, elapsed_s=7 * 3600).thread.is_alive = lambda: False
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: None)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["game_uptime_s"] is None
    assert snapshot["restart_elapsed_s"] is None
    assert snapshot["restart_source"] == "unavailable"
    assert snapshot["restart_interval_s"] == 6 * 3600


def test_game_absence_is_distinct_from_an_unreadable_process_age(application, monkeypatch):
    monkeypatch.setattr(process, "find_game_process", lambda: None)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["game_running"] is False
    assert snapshot["game_uptime_s"] is None
    assert snapshot["restart_source"] == "unavailable"


def test_process_query_failure_keeps_running_state_unknown(application, monkeypatch):
    def denied():
        raise PermissionError("process inspection denied")

    monkeypatch.setattr(process, "find_game_process", denied)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["game_running"] is None
    assert snapshot["game_uptime_s"] is None
    assert snapshot["restart_elapsed_s"] is None


def test_starting_runner_does_not_invent_uninitialized_clocks(application, monkeypatch):
    runner = runner_mod.Runner.__new__(runner_mod.Runner)
    runner.thread = SimpleNamespace(is_alive=lambda: True)
    application.runner = runner
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: None)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["restart_elapsed_s"] is None
    assert snapshot["restart_interval_s"] is None
    assert snapshot["restart_source"] == "unavailable"


@pytest.mark.parametrize("interval", ["0", "invalid", "nan", "inf"])
def test_disabled_restart_and_legacy_intervals_remain_honest(application, monkeypatch, interval):
    application.settings.set("RestartGame", "0")
    application.settings.set("RestartGameTest", "1")
    application.settings.set("RestartGameTime", interval)
    monkeypatch.setattr(process, "game_uptime_s", lambda proc=None: 300.0)
    snapshot = application.game_runtime_snapshot()
    assert snapshot["restart_enabled"] is False
    assert snapshot["restart_test"] is True
    assert snapshot["game_uptime_s"] == 300
    assert snapshot["restart_interval_s"] == (0 if interval == "0" else None)
    assert application.settings.get("RestartGameTime") == interval


def test_app_wires_runtime_reader_without_starting_the_game(monkeypatch, tmp_path):
    class Window:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(app_mod, "MainWindow", Window)
    monkeypatch.setattr(app_mod, "base_dir", lambda: str(tmp_path))
    monkeypatch.setattr(app_mod, "set_dpi_aware", lambda: "test")
    monkeypatch.setattr(app_mod.App, "_close_splash", lambda self: None)
    monkeypatch.delenv("FIRESTONE_GUI_PAGE", raising=False)
    monkeypatch.delenv("FIRESTONE_GUI_APPEARANCE", raising=False)
    app = app_mod.App()
    assert app.window.on_game_runtime == app.game_runtime_snapshot
    assert app.runner is None and app.game is None
