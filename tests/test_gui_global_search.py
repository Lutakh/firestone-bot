"""Search reveals real controls without executing commands or mutating settings."""

import threading
import time
import tkinter as tk

import pytest

pytest.importorskip("customtkinter")

from firestone_bot.gui import theme
from firestone_bot.gui.catalog import OPTIONS
from firestone_bot.gui.main_window import MainWindow
from firestone_bot.gui.search_catalog import SEARCH_TARGETS, search_launcher
from firestone_bot.settings import Settings


@pytest.fixture(scope="module")
def launcher(tmp_path_factory):
    directory = tmp_path_factory.mktemp("global-search")
    settings = Settings(path=str(directory / "settings.ini"), loaded=True)
    calls, errors = [], []
    running = {"value": False}
    try:
        window = MainWindow(
            settings,
            on_start=lambda: calls.append("start"),
            on_stop=lambda: calls.append("stop"),
            on_dry_run=lambda: calls.append("dry_run"),
            on_self_test=dict,
            on_exit=lambda: None,
            is_running=lambda: running["value"],
            base_dir=str(directory),
        )
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    window.root.geometry("980x680")
    window._last_selftest = time.time()
    window.root.report_callback_exception = lambda *args: errors.append(args)
    window.test_calls, window.test_errors, window.test_running = calls, errors, running
    for name in (
        "check_updates",
        "install_update",
        "rollback_update",
        "save_now",
        "reload",
        "import_settings",
        "open_folder",
        "open_log",
        "refresh_status",
    ):
        window.ctx.callbacks[name] = lambda name=name: calls.append(name)
    yield window
    window.request_exit()
    assert not errors


def settle(root, ms=250):
    done = tk.BooleanVar(master=root, value=False)
    root.after(ms, lambda: done.set(True))
    root.wait_variable(done)
    root.update_idletasks()


def assert_in_view(target, viewport):
    assert target.winfo_ismapped()
    y = target.winfo_rooty()
    assert y >= viewport.winfo_rooty()
    assert y + target.winfo_height() <= viewport.winfo_rooty() + viewport.winfo_height()


def test_every_destination_resolves_to_a_real_widget_without_invoking_it(launcher, monkeypatch):
    window = launcher
    seen = []

    def capture(scrollable, target):
        assert target.winfo_exists()
        seen.append((scrollable, target))

    for module in ("main_window", "pages.automations", "pages.workshop"):
        monkeypatch.setattr(f"firestone_bot.gui.{module}.reveal_widget", capture)
    # Build before taking the value snapshot: constructing legacy controls can register defaults.
    for result in SEARCH_TARGETS:
        window.open_search_result(result)
    window.root.update()
    before = {key: window.settings.get(key) for key in OPTIONS}
    calls = list(window.test_calls)
    seen.clear()
    for result in SEARCH_TARGETS:
        window.open_search_result(result)
        window.root.update_idletasks()
        assert window.current_page == result.page, result.id
        if result.id.startswith("page:"):
            assert not seen
            continue
        assert len(seen) == 1, result.id
        scrollable, target = seen.pop()
        assert target.winfo_ismapped(), result.id
        if result.page in ("automations", "workshop"):
            assert scrollable is not None, result.id
    assert {key: window.settings.get(key) for key in OPTIONS} == before
    assert window.test_calls == calls
    assert not window.test_errors


def test_update_enter_scrolls_to_real_button_and_does_not_install(launcher):
    window = launcher
    window.show_page("camp")
    search = window.search
    settle(window.root)
    original_height = window.content.winfo_height()
    search.focus_search()
    search.query_var.set("update")
    # Enter before the debounce fires still resolves the latest query.
    search._activate()
    settle(window.root)
    assert window.current_page == "workshop"
    workshop = window.ctx.extras["workshop"]
    assert workshop.section == "files"
    target = workshop.actions["check_update"]
    assert_in_view(target, workshop.panels["files"]._parent_canvas)
    assert not search.popup.winfo_ismapped()
    assert window.content.winfo_height() == original_height
    assert not window.test_calls
    assert target.cget("text") == "Check for updates now"


def test_popup_keyboard_all_results_clear_and_no_match(launcher):
    window = launcher
    window.show_page("camp")
    search = window.search
    settle(window.root)
    height = window.content.winfo_height()
    search.focus_search()
    search.query_var.set("a")
    search.refresh_results()
    settle(window.root)
    assert len(search.results) > 30
    assert search.results == search_launcher("a", limit=None)
    assert search.popup.winfo_ismapped()
    for button in search._result_buttons:
        assert button._text_label.winfo_reqheight() <= button.winfo_height() - 4
    assert window.content.winfo_height() == height
    assert_in_view(search.popup, window.root)
    search._move(-1)
    settle(window.root)
    assert search._selected_index == len(search.results) - 1
    assert_in_view(search._result_buttons[-1], search.library._parent_canvas)
    search._move(1)
    settle(window.root)
    assert search._selected_index == 0
    assert_in_view(search._result_buttons[0], search.library._parent_canvas)
    search._escape()
    assert not search.popup.winfo_ismapped() and search.query_var.get() == "a"
    search.query_var.set("nothing matches this unusual phrase")
    search.refresh_results()
    settle(window.root)
    assert not search.results and search.empty_label.winfo_ismapped()
    search._activate()
    assert window.current_page == "camp"
    search.clear_button.invoke()
    assert not search.query_var.get() and not search.popup.winfo_ismapped()
    assert not window.test_errors


def test_pending_reveal_and_search_callbacks_are_released_across_skins(launcher):
    window = launcher
    baseline = None
    for skin in theme.SKIN_NAMES:
        window.open_search_result(search_launcher("update")[0])
        old_search = window.search
        query = old_search.query_var
        query.set("restart")
        old_search.refresh_results()
        query.set("alchemy")  # leave a debounce pending when rebuilding
        window.set_skin(
            skin
            if theme.current_skin() != skin
            else next(name for name in theme.SKIN_NAMES if name != skin)
        )
        settle(window.root)
        assert not old_search._alive and not query.trace_info()
        assert not old_search.popup.winfo_exists()
        assert all(
            getattr(old_search, name) is None
            for name in ("_search_after", "_position_after", "_reveal_after")
        )
        counts = tuple(
            sum(bool(line.strip()) for line in window.root.bind(sequence).splitlines())
            for sequence in ("<Button-1>", "<Configure>")
        )
        baseline = baseline or counts
        assert counts == baseline
        assert not window.test_errors


@pytest.mark.parametrize("running", [False, True])
def test_runtime_polls_on_worker_while_idle_and_running(launcher, running):
    window = launcher
    window.test_running["value"] = running
    inspected = threading.Event()
    release = threading.Event()
    thread_ids = []
    snapshot = {
        "game_uptime_s": 3661,
        "game_running": True,
        "restart_enabled": False,
        "observed_at": time.monotonic(),
    }

    def read():
        thread_ids.append(threading.get_ident())
        inspected.set()
        release.wait(2)
        return snapshot

    window.on_game_runtime = read
    try:
        window._last_runtime_poll = window._last_second = 0
        window._poll()
        assert inspected.wait(1)
        window._refresh_game_runtime()
        assert len(thread_ids) == 1 and thread_ids[0] != threading.get_ident()
        release.set()
        settle(window.root)
        assert window.game_runtime == snapshot
        assert not window._runtime_inflight
        assert window.dash.runtime_value.cget("text").startswith("Game uptime: 01h 01m")
    finally:
        release.set()
        window.on_game_runtime = None
        window.test_running["value"] = False


@pytest.mark.parametrize(
    "query",
    ["UpgradeH5", "Heal", "Priority5", "SellNone", "heroes:all", "ClientID", "display mode"],
)
def test_composite_and_read_only_destinations_are_revealed_without_edits(
    launcher, monkeypatch, query
):
    from firestone_bot.gui.widgets import reveal_widget

    window = launcher
    result = search_launcher(query)[0]
    captured = []

    def reveal(scrollable, target):
        captured.append((scrollable, target))
        reveal_widget(scrollable, target)

    for module in ("pages.automations", "pages.workshop"):
        monkeypatch.setattr(f"firestone_bot.gui.{module}.reveal_widget", reveal)
    before = {key: window.settings.get(key) for key in OPTIONS}
    appearance = window.appearance_var.get()
    calls = list(window.test_calls)
    window.open_search_result(result)
    settle(window.root)
    assert len(captured) == 1
    scrollable, target = captured[0]
    assert_in_view(target, scrollable._parent_canvas)
    assert {key: window.settings.get(key) for key in OPTIONS} == before
    assert window.appearance_var.get() == appearance
    assert window.test_calls == calls
    assert not window.test_errors
