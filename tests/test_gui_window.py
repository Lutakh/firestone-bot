"""GUI smoke test: builds the customtkinter window headlessly (skipped without a display)."""

import json
import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter")

from firestone_bot.gui import theme
from firestone_bot.gui.automation_catalog import AUTOMATIONS, WORKSHOP_GROUPS
from firestone_bot.gui.catalog import READ_ONLY_KEYS
from firestone_bot.gui.main_window import MainWindow
from firestone_bot.gui.pages import PAGE_ORDER
from firestone_bot.settings import EXTRA_SETTINGS, SETTINGS_MAP, Settings


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """One root per module: a second Tk root in the same process is flaky on Windows."""
    tmp_path = tmp_path_factory.mktemp("gui")
    (tmp_path / "gui_state.json").write_text(
        json.dumps({"page": "workshop", "workshop_section": "game"}), encoding="utf-8"
    )
    settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    calls = []
    flags = {"running": False}
    try:
        win = MainWindow(
            settings,
            on_start=lambda: calls.append("start"),
            on_stop=lambda: calls.append("stop"),
            on_dry_run=lambda: calls.append("dry"),
            on_self_test=lambda: {
                "window": "not found (no game)",
                "platform": "-",
                "client": "-",
                "scale": "-",
                "dpi": "per-monitor-v2",
                "capture": "-",
            },
            on_exit=lambda: calls.append("exit"),
            is_running=lambda: flags["running"],
            base_dir=str(tmp_path),
        )
    except tk.TclError as e:
        pytest.skip(f"no display: {e}")
    win.calls = calls
    win.flags = flags
    yield win
    if not win._closed:
        win.root.destroy()


def test_startup_opens_camp_instead_of_the_saved_page(window):
    assert window.current_page == "camp"
    assert window.gui_state["page"] == "camp"
    assert window.gui_state["workshop_section"] == "game"


def test_pages_build_and_every_key_is_bound(window):
    for name in PAGE_ORDER:
        window.show_page(name)
        window.root.update()
    assert window.current_page == PAGE_ORDER[-1]
    for group in AUTOMATIONS:
        window.ctx.extras["automations"].open_group(group.id)
    for group in WORKSHOP_GROUPS:
        window.ctx.extras["workshop"].open_section(group.id)
    window.root.update()
    assert window.binder.keys() | READ_ONLY_KEYS == set(SETTINGS_MAP) | set(EXTRA_SETTINGS)


def test_status_from_worker_thread_and_self_test(window):
    t = threading.Thread(target=window.post_status, args=("Cycle 2 done, waiting 60 s",))
    t.start()
    t.join()
    window._tick()
    window.root.update()
    assert window.dash.activity_label.cget("text") == "Cycle 2 done, waiting 60 s"
    assert window.cycle == 2
    window.refresh_status()
    for _ in range(40):
        window._tick()
        window.root.update()
        if window.dash.env_values["window"].cget("text").startswith("not found"):
            break
        time.sleep(0.05)
    assert window.dash.env_values["window"].cget("text") == "not found (no game)"
    assert window.dash.window_banner._visible


def _buttons(window):
    return tuple(b.cget("state") for b in (window.start_btn, window.dry_btn, window.stop_btn))


def test_runner_thread_dead_before_first_poll_resets_buttons(window):
    # e.g. RestartGameTest=1 with the game closed: the thread crashes before any sleep
    window.flags["running"] = True
    window.set_bot_state("running")
    assert _buttons(window) == ("disabled", "disabled", "normal")
    window.flags["running"] = False
    window.post_status("Crashed, see log")
    window._tick()
    window.root.update()
    assert window.bot_state == "crashed"
    assert _buttons(window) == ("normal", "normal", "disabled")
    # same without any terminal status line: the 0.5 s poll notices the dead thread
    window.flags["running"] = True
    window.set_bot_state("dry run (no input)")
    assert window.activity_text == "Starting…"  # the old "Crashed" line is forgotten
    window.flags["running"] = False
    window._last_poll = 0.0
    window._tick()
    assert window.bot_state == "stopped"
    assert _buttons(window) == ("normal", "normal", "disabled")


def test_tick_survives_a_bad_queue_message(window):
    window.ui_queue.put(("selftest", None))  # TypeError inside _apply_selftest
    window.ui_queue.put(("activity", "still alive"))
    window._tick()
    assert window.activity_text == "still alive"
    # the bare post_status line reaches the Activity log (the logged traceback follows it)
    assert any(line.endswith("still alive") for line in window.dash._lines)


def test_skin_switch_preserves_active_settings_runtime_and_logs(window):
    window.flags["running"] = True
    window.set_bot_state("running")
    window._on_activity("Cycle 7 done in 42s, waiting 60 s")
    window.show_page("journal")
    journal = window.ctx.extras["journal"]
    journal.clear_log()
    window._append_log("A real queued message")
    lines = list(window.log_lines)
    settings = window.settings
    binder = window.binder
    variable = binder.var("Alch", inverted=True)
    variable.set("0")
    binder.flush()
    assert binder.dirty and window._save_state[0] == "deferred"
    calls = list(window.calls)

    for skin in ("Retro", "Futuristic", "Fieldbook"):
        old_journal = window.ctx.extras["journal"]
        window.set_skin(skin)
        window.root.update()
        assert theme.current_skin() == skin
        assert window.current_page == "journal"
        assert window.ctx.extras["journal"] is not old_journal
        assert window.settings is settings and window.binder is binder
        assert settings.get("Alch") == "1" and variable.get() == "0"
        assert binder.dirty and window._save_state[0] == "deferred"
        assert list(window.log_lines) == lines
        assert window.bot_state == "running" and window.cycle == 7
        assert window.cycle_duration == "42s"
        assert _buttons(window) == ("disabled", "disabled", "normal")
        assert window.calls == calls
        assert "A real queued message" in window.ctx.extras["journal"].textbox.get("1.0", "end")
        assert len(variable.trace_info()) == 1  # only Binder survives; no destroyed editor
        saved = json.loads(Path(window.state_path).read_text(encoding="utf-8"))
        assert saved["skin"] == skin and saved["page"] == "journal"
        assert int(window.skin_menu.grid_info()["column"]) == 4
        assert int(window.nav_buttons["workshop"].grid_info()["column"]) == 3
        assert int(window.nav_buttons["camp"].grid_info()["column"]) == 0

    window.flags["running"] = False
    window._on_activity("Stopped")
    assert not binder.dirty
    assert Settings.load(settings.path).get("Alch") == "1"


def test_session_commands_and_workshop_jump_use_real_callbacks(window):
    before = len(window.calls)
    window.start_btn.invoke()
    window.dry_btn.invoke()
    window.flags["running"] = True
    window.set_bot_state("running")
    window.stop_btn.invoke()
    assert window.calls[before:] == ["start", "dry", "stop"]
    window.flags["running"] = False
    window._on_activity("Stopped")
    window.open_workshop("heartbeat")
    assert window.current_page == "workshop"
    assert window.ctx.extras["workshop"].section == "heartbeat"
    window.open_automation("alchemy")
    assert window.current_page == "automations"


def test_journal_clear_is_view_only_and_skin_retains_update_banner(window):
    window.show_page("journal")
    journal = window.ctx.extras["journal"]
    window._append_log("First message\ncontinued detail")
    assert "continued detail" in journal.textbox.get("1.0", "end")
    window.show_update("An update is available", "Install update")
    window.set_skin("Retro")
    window.root.update()
    assert window.top_banner_text.cget("text") == "An update is available"
    assert window.top_banner_btn.cget("text") == "Install update"
    assert window.top_banner.winfo_manager()
    journal = window.ctx.extras["journal"]
    journal.clear_log()
    assert not window.log_lines
    assert "No activity yet" in journal.textbox.get("1.0", "end")
    window.show_update("")
    window.set_skin("Fieldbook")
    assert not window.top_banner.winfo_manager()


def test_camp_keeps_persisted_cycle_statistics_across_skins(window):
    window.settings.set("CyclesTotal", "3")
    window.settings.set("CycleMsTotal", "180000")
    window.settings.set("LastCycleMs", "75000")
    window.cycle_duration = ""
    window.show_page("camp")
    for skin in ("Retro", "Fieldbook"):
        window.set_skin(skin)
        window.dash.refresh_today()
        assert window.dash.stat_values["cycles"].cget("text") == "3"
        assert window.dash.stat_values["average"].cget("text") == "1m00s"
        assert window.dash.stat_values["total"].cget("text") == "3m00s"
        assert window.dash.cycle_value.cget("text") == "1m15s"


def test_request_exit_from_thread_calls_on_exit(window):
    # Must stay the last test of the module: it destroys the shared root.
    t = threading.Thread(target=window.request_exit)
    t.start()
    t.join()
    window._tick()
    assert window.calls[-1] == "exit"
    assert window._closed
