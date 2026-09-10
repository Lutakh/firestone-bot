"""Camp keeps real values visible in one screen, including warning and locked states."""

import json
import time
import tkinter as tk
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter")

from firestone_bot.gui import theme
from firestone_bot.gui.main_window import MainWindow
from firestone_bot.gui.pages.dashboard import DashboardView
from firestone_bot.settings import Settings

ENVIRONMENT = {
    "window": "'Firestone' pid 12345 maximized (restored from minimised)",
    "platform": "steam",
    "client": "3024x1701 at (0,50)",
    "scale": "1.575 (canvas 1.575), aspect differs from reference: anchors in use",
    "dpi": "macOS, 2 px per point (capture in pixels, input in points)",
    "capture": "OK 3024x1701 in 42 ms",
    "input": "pynput CGEvent, Accessibility granted (move test happens in the dry run trace)",
}


@pytest.fixture(scope="module")
def camp_window(tmp_path_factory):
    folder = tmp_path_factory.mktemp("camp")
    settings = Settings(path=str(folder / "settings.ini"), loaded=True)
    for key, value in {
        "CyclesTotal": "12345",
        "CycleMsTotal": "555555000",
        "LastCycleMs": "75000",
        "TokenCountDaily": "4",
        "MaxTokens": "10",
        "ChaosCountDaily": "2",
        "ScarabCountDaily": "3",
        "CrystalCountDaily": "1",
        "LastTokenReset": "20260910060000",
    }.items():
        settings.set(key, value)
    try:
        window = MainWindow(
            settings,
            on_start=lambda: None,
            on_stop=lambda: None,
            on_dry_run=lambda: None,
            on_self_test=lambda: ENVIRONMENT,
            on_exit=lambda: None,
            is_running=lambda: False,
            base_dir=str(folder),
        )
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    window._last_selftest = time.time()
    window.errors = []
    window.root.report_callback_exception = lambda *args: window.errors.append(args)
    yield window
    window.request_exit()


def _settle(root):
    done = tk.BooleanVar(master=root, value=False)
    root.after(250, lambda: done.set(True))
    root.wait_variable(done)
    root.update_idletasks()


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _assert_visible(widget, viewport):
    assert widget.winfo_ismapped(), widget
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    right = x + widget.winfo_width()
    bottom = y + widget.winfo_height()
    assert x >= viewport.winfo_rootx(), widget
    assert y >= viewport.winfo_rooty(), widget
    assert right <= viewport.winfo_rootx() + viewport.winfo_width(), (widget, right)
    assert bottom <= viewport.winfo_rooty() + viewport.winfo_height(), (widget, bottom)
    assert widget.winfo_height() >= widget.winfo_reqheight(), widget


@pytest.mark.parametrize("skin", theme.SKIN_NAMES)
@pytest.mark.parametrize("geometry", ("1220x860", "980x680"))
def test_camp_values_fit_without_scrolling(camp_window, skin, geometry):
    window = camp_window
    window.root.geometry(geometry)
    window.set_skin(skin)
    window.show_page("camp")
    window.show_update("Version 0.3.17 is available", "Update", "warn")
    view = window.dash
    assert not isinstance(view.frame, ctk.CTkScrollableFrame)
    assert not any(
        isinstance(widget, ctk.CTkButton) and widget.cget("text") == "Files & application"
        for widget in _descendants(view.frame)
    )
    for missing in (False, True):
        Path(window.base_dir, "progress.json").write_text(
            json.dumps(
                {"account_level": 45 if missing else 200, "guild_level": 3 if missing else 5}
            ),
            encoding="utf-8",
        )
        window.game_runtime = {
            "game_uptime_s": None if missing else 98765,
            "game_running": not missing,
            "restart_elapsed_s": 999,
            "restart_source": "bot" if missing else "game",
            "restart_interval_s": 86400,
            "restart_enabled": True,
            "observed_at": time.monotonic(),
        }
        view.refresh_today()
        environment = {**ENVIRONMENT}
        if missing:
            environment["window"] = "not found (start Firestone, maximized, then Re-check)"
        view.env_result(environment, "Last checked 12:34:56 · auto-refresh every 30 s while idle")
        view.set_state("Crashed" if missing else "Idle", "err" if missing else "grey", 123, "1m15s")
        view.set_activity("Alchemy: collecting completed experiments and starting new research")
        _settle(window.root)
        for widget in view.sections.values():
            _assert_visible(widget, window.content)
        for widget in _descendants(view.frame):
            if isinstance(widget, (ctk.CTkLabel, ctk.CTkButton)) and widget.winfo_ismapped():
                _assert_visible(widget, window.content)
                # A parent card must not clip a label that is otherwise inside the window.
                _assert_visible(widget, widget.master)
        assert view.stat_values["cycles"].cget("text") == "12345"
        assert view.cycle_value.cget("text") == "1m15s"
        assert view.meter_tokens.value.cget("text") == "4 / 10"
        assert view.level_values["account_level"].cget("text") == ("45" if missing else "200")
        assert view.meter_chaos.value.cget("text") == (
            "Locked (level 100)" if missing else "2 / 10"
        )
        assert view.window_banner._visible == missing
        assert not window.errors


def test_destroyed_camp_releases_its_refresh_callback(camp_window):
    window = camp_window
    callbacks = list(window._tick_fns)
    view = DashboardView(window.content, window.ctx)
    assert len(window._tick_fns) == len(callbacks) + 1
    view.frame.destroy()
    assert window._tick_fns == callbacks
