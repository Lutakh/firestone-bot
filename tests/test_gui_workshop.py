"""Workshop integration: real bindings, maintenance guards and preserved view state."""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

import pytest

ctk = pytest.importorskip("customtkinter")

from firestone_bot.gui import theme
from firestone_bot.gui.automation_catalog import WORKSHOP_GROUPS
from firestone_bot.gui.binding import Binder
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.pages.workshop import Workshop
from firestone_bot.settings import Settings


@pytest.fixture(scope="module")
def workshop(tmp_path_factory):
    folder = tmp_path_factory.mktemp("workshop")
    settings = Settings(path=str(folder / "settings.ini"), loaded=True)
    settings.set("Talents450", "legacy value")
    settings.set("ClientID", "test-client-id")
    theme.set_skin("Fieldbook")
    try:
        root = ctk.CTk()
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    root.geometry("1100x850")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    flags = {"running": False}
    calls = []
    ticks = []

    def register_tick(callback):
        ticks.append(callback)
        return lambda: ticks.remove(callback)

    binder = Binder(settings, root, lambda *args: None, lambda: flags["running"])
    window = SimpleNamespace(gui_state={}, update_text="", update_button=None, update_kind="info")
    callbacks = {
        name: lambda callback=name: calls.append(callback)
        for name in (
            "save_now",
            "reload",
            "import_settings",
            "open_folder",
            "open_log",
            "refresh_status",
            "check_updates",
            "install_update",
            "rollback_update",
        )
    }
    callbacks["is_running"] = lambda: flags["running"]
    ctx = PageContext(
        settings,
        binder,
        callbacks,
        lambda name: None,
        str(folder),
        register_tick,
        root=root,
        window=window,
        extras={"appearance_var": tk.StringVar(value="System"), "previous_version": "0.3.10"},
    )
    controller = Workshop(root, ctx)
    controller.widget.grid(row=0, column=0, sticky="nsew")
    root.update()
    controller.test_state = SimpleNamespace(
        calls=calls,
        flags=flags,
        ticks=ticks,
        errors=errors,
    )
    yield controller
    binder.flush(force=True)
    root.destroy()
    assert not errors


def refresh(workshop):
    for callback in tuple(workshop.test_state.ticks):
        callback()
    workshop.ctx.root.update()


def test_every_workshop_setting_is_bound_without_rewriting_legacy_values(workshop):
    for group in WORKSHOP_GROUPS:
        workshop.open_section(group.id)
        workshop.ctx.root.update()
    expected = {key for group in WORKSHOP_GROUPS for key in group.keys}
    assert workshop.ctx.binder.keys() == expected
    assert workshop.ctx.settings.get("Talents450") == "legacy value"
    assert "Talents450" not in workshop.controls
    assert "Talents800" not in workshop.controls


def test_restart_and_heartbeat_dependencies_follow_the_current_click(workshop):
    restart = workshop.controls["RestartGame"].control
    interval = workshop.controls["RestartGameTime"].control.widget
    once = workshop.controls["RestartGameTest"].control.widget
    for value, state in (("0", "disabled"), ("1", "normal"), ("0", "disabled")):
        restart.var.set(value)
        assert all(button.cget("state") == state for button in interval._buttons_dict.values())
        assert once.cget("state") == state
        assert workshop.ctx.settings.get("RestartGame") == value
    heartbeat = workshop.controls["EnableHeartbeat"].control
    discord = workshop.controls["DiscordID"].control.widget
    for value, state in (("1", "normal"), ("0", "disabled")):
        heartbeat.var.set(value)
        assert discord.cget("state") == state


def test_file_callbacks_and_update_availability(workshop):
    workshop.open_section("files")
    state = workshop.test_state
    state.calls.clear()
    for key in ("save", "reload", "import", "folder", "log", "check_update", "rollback"):
        workshop.actions[key].invoke()
    assert state.calls == [
        "save_now",
        "reload",
        "import_settings",
        "open_folder",
        "open_log",
        "check_updates",
        "rollback_update",
    ]
    install = workshop.actions["install_update"]
    assert install.cget("state") == "disabled"
    workshop.ctx.window.update_text = "Version 0.3.12 is available."
    workshop.ctx.window.update_button = "Update to 0.3.12"
    refresh(workshop)
    assert install.cget("state") == "normal"
    assert install.cget("text") == "Update to 0.3.12"
    assert workshop.update_label.cget("text") == "Version 0.3.12 is available."
    install.invoke()
    assert state.calls[-1] == "install_update"
    state.flags["running"] = True
    refresh(workshop)
    count = len(state.calls)
    for key in ("reload", "import", "reset", "rollback", "install_update"):
        assert workshop.actions[key].cget("state") == "disabled"
        # Calling the Tcl command directly also has to respect the runtime guard.
        workshop.actions[key].cget("command")()
    assert len(state.calls) == count
    state.flags["running"] = False
    refresh(workshop)


def test_counter_reset_preserves_quotas_and_resets_every_daily_marker(workshop, monkeypatch):
    confirmations = []
    monkeypatch.setattr(
        "firestone_bot.gui.pages.workshop.messagebox.askyesno",
        lambda *args, **kwargs: confirmations.append(args) or True,
    )
    settings = workshop.ctx.settings
    counters = (
        "TokenCountDaily",
        "ChaosCountDaily",
        "ScarabCountDaily",
        "CrystalCountDaily",
        "ArenaDoneDaily",
        "ChaosBooksDaily",
    )
    for key in counters:
        settings.set(key, "3")
    settings.set("MaxTokens", "12")
    settings.set("MaxCrystals", "5")
    workshop.test_state.flags["running"] = True
    workshop.reset_counters()
    assert not confirmations
    assert settings.get("TokenCountDaily") == "3"
    workshop.test_state.flags["running"] = False
    workshop.reset_counters()
    assert len(confirmations) == 1
    assert all(settings.get(key) == "0" for key in counters)
    assert settings.get("LastTokenReset") == settings.get("LastChaosReset")
    reloaded = Settings.load(settings.path)
    assert all(reloaded.get(key) == "0" for key in counters)
    assert reloaded.get("MaxTokens") == "12"
    assert reloaded.get("MaxCrystals") == "5"


def test_sections_are_cached_and_selection_is_restorable(workshop):
    workshop.open_section("game")
    page = workshop.panels["game"]
    workshop.actions["environment"].invoke()
    assert workshop.test_state.calls[-1] == "refresh_status"
    workshop.open_section("help")
    workshop.open_section("game")
    assert workshop.panels["game"] is page
    assert workshop.ctx.window.gui_state["workshop_section"] == "game"
    assert workshop.ctx.extras["workshop_section"] == "game"
    workshop.open_section("application")
    assert workshop.section == "files"
    workshop.open_section("unknown old section")
    assert workshop.section == "session"


def test_destroyed_workshop_releases_view_callbacks(workshop):
    # Last test: all UI traces go away, while Binder variables remain usable by a new skin.
    workshop.widget.destroy()
    assert not workshop.test_state.ticks
    for key, (variable, _inverted) in workshop.ctx.binder._vars.items():
        assert len(variable.trace_info()) == 1, key
        variable.set(variable.get())
    workshop.ctx.root.update()
