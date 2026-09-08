"""GUI smoke test: builds the customtkinter window headlessly (skipped without a display)."""

import threading
import time
import tkinter as tk

import pytest

ctk = pytest.importorskip("customtkinter")

from firestone_bot.gui.catalog import READ_ONLY_KEYS
from firestone_bot.gui.main_window import MainWindow
from firestone_bot.gui.pages import PAGE_ORDER
from firestone_bot.settings import EXTRA_SETTINGS, SETTINGS_MAP, Settings


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """One root per module: a second Tk root in the same process is flaky on Windows."""
    tmp_path = tmp_path_factory.mktemp("gui")
    settings = Settings(path=str(tmp_path / "settings.ini"))
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


def test_pages_build_and_every_key_is_bound(window):
    for name in PAGE_ORDER:
        window.show_page(name)
        window.root.update()
    assert window.current_page == PAGE_ORDER[-1]
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


def test_routine_navigation_keeps_session_controls_visible(window):
    for page, button in window.dash.routine_buttons.items():
        window.show_page("dashboard")
        button.invoke()
        window.root.update()
        assert window.current_page == page
        assert window.session.winfo_ismapped()
        assert window.start_btn.winfo_ismapped()
        assert window.stop_btn.winfo_ismapped()
    window.show_dashboard_tab("Journal")
    window.dash.append_log("Retro journal navigation test")
    window.root.update()
    assert window.dash.tabs.get() == "Journal"
    assert "Retro journal navigation test" in window.session.recent.get("1.0", "end")
    window.dash.clear_log()
    assert window.session.recent.get("1.0", "end").strip() == "No activity yet."


def test_compact_window_and_appearance_preserve_controls(window):
    from firestone_bot.gui.widgets import Card

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    window.root.geometry("1100x720")
    for appearance in ("light", "dark"):
        window.set_appearance(appearance)
        for page in PAGE_ORDER:
            window.show_page(page)
            window.root.update()
            # Wait for the coalesced text wrapping after this size change.
            settled = tk.BooleanVar(value=False)
            window.root.after(180, lambda settled=settled: settled.set(True))
            window.root.wait_variable(settled)
            window.root.update()
            stop = window.stop_btn
            assert stop.winfo_rootx() >= window.root.winfo_rootx()
            assert stop.winfo_rooty() + stop.winfo_height() <= (
                window.root.winfo_rooty() + window.root.winfo_height()
            )
            assert window.session.winfo_width() >= 290
            for widget in descendants(window.pages[page]):
                if isinstance(widget, Card) and widget.winfo_ismapped():
                    assert widget.winfo_width() <= window.content.winfo_width()
    window.set_appearance("light")
    window.root.geometry("1360x860")


def test_tk9_dropdown_redraw_does_not_reenter_idle_loop(window):
    from firestone_bot.gui.widgets import MAC_TK9, _OptionMenu

    if not MAC_TK9:
        pytest.skip("macOS Tk 9 layout compatibility")

    menu = _OptionMenu(window.content, values=["One", "Two"])
    idle_calls = []
    window.root.after_idle(lambda: idle_calls.append(True))
    menu.configure(state="disabled")
    assert not idle_calls  # A redraw must not recursively lay out a partially built page.
    window.root.update()
    assert idle_calls == [True]
    menu.destroy()


def test_request_exit_from_thread_calls_on_exit(window):
    # Must stay the last test of the module: it destroys the shared root.
    t = threading.Thread(target=window.request_exit)
    t.start()
    t.join()
    window._tick()
    assert window.calls == ["exit"]
    assert window._closed
