"""Native Fieldbook shell, skin selection, session commands and runtime state.

Threading contract: only the main thread touches Tk. Worker threads (bot, self-test, hotkey
listener, logging) put messages on `ui_queue`; `_tick` drains it every 150 ms.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections import deque
from collections.abc import Callable
from tkinter import messagebox

import customtkinter as ctk

from firestone_bot import __version__
from firestone_bot.gui import theme
from firestone_bot.gui.binding import Binder
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.logging_bridge import QueueLogHandler
from firestone_bot.gui.pages import PAGE_ORDER, PAGE_TITLES, build
from firestone_bot.gui.widgets import OptionMenu, StatePill, StatusDot, apply_window_icon, autowrap
from firestone_bot.platform import capture
from firestone_bot.settings import Settings

log = logging.getLogger("firestone_bot.gui")

DEFAULT_GEOMETRY = "1220x860"
MIN_SIZE = (980, 680)
MAX_LOG_LINES = 2000
SELFTEST_PERIOD = 30.0
SELFTEST_TIMEOUT = 10.0
APPEARANCES = ["System", "Light", "Dark"]

# bot state -> (pill text, colour kind)
STATES = {
    "idle": ("Idle", "grey"),
    "stopped": ("Stopped", "grey"),
    "running": ("Running", "ok"),
    "dry": ("Dry run (no input)", "info"),
    "stopping": ("Stopping…", "warn"),
    "crashed": ("Crashed - see log", "err"),
    "delay": ("Stopped - Delay setting not recognised", "warn"),
}
# final status lines of Runner._run / main_script -> bot state
TERMINAL_STATES = {"Crashed, see log": "crashed", "Stopped": "stopped"}
SAVE_KINDS = {"unsaved": "muted", "deferred": "info", "saved": "ok", "error": "err"}


def _load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


class MainWindow:
    def __init__(
        self,
        settings: Settings,
        *,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_dry_run: Callable[[], None],
        on_self_test: Callable[[], dict[str, str]],
        on_exit: Callable[[], None],
        is_running: Callable[[], bool] = lambda: False,
        base_dir: str | None = None,
    ) -> None:
        self.settings = settings
        self.on_start, self.on_stop, self.on_dry_run = on_start, on_stop, on_dry_run
        self.on_self_test, self.on_exit = on_self_test, on_exit
        self.on_env_restored = None  # set by the app: raise the window after a restore
        self.is_running = is_running
        self.base_dir = base_dir or os.getcwd()
        self.state_path = os.path.join(self.base_dir, "gui_state.json")
        self.gui_state = _load_state(self.state_path)
        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._closed = False

        appearance = str(self.gui_state.get("appearance") or "light")
        ctk.set_appearance_mode(appearance)
        saved_skin = str(self.gui_state.get("skin") or "Fieldbook")
        theme.set_skin(saved_skin if saved_skin in theme.SKIN_NAMES else "Fieldbook")
        self.root = ctk.CTk()
        self.root.report_callback_exception = lambda exc, val, tb: log.error(
            "Tk callback failed", exc_info=(exc, val, tb)
        )
        self.root.title(f"Firestone Bot {__version__}")
        self.root.minsize(*MIN_SIZE)
        self.root.geometry(self._initial_geometry())
        self.root.protocol("WM_DELETE_WINDOW", self.request_exit)

        self.binder = Binder(settings, self.root, self._on_save_state, is_running)
        self.binder.on_save_error = self._save_error_dialog
        self.log_handler = QueueLogHandler(self.ui_queue)
        logging.getLogger("firestone_bot").addHandler(self.log_handler)

        self.appearance_var = tk.StringVar(value=appearance.capitalize())
        self.appearance_var.trace_add("write", lambda *_: self._apply_appearance())

        # runtime model
        self.bot_state = "idle"
        self.activity_text = "Idle"
        self.cycle: int | None = None
        self.cycle_duration = ""
        self._was_running = False
        self._selftest_inflight = False
        self._selftest_started = 0.0
        self._selftest_gen = 0  # a late result from an older (timed-out) worker is ignored
        self._selftest_outstanding = 0  # workers started and not yet returned
        self._last_selftest = 0.0
        self._recent_logs: deque[str] = deque(maxlen=50)
        self.log_lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.log_follow = True
        self.log_scroll = 0.0
        self._save_state = ("saved", "Settings loaded")
        self.update_text = ""
        self.update_button: str | None = None
        self.update_kind = "info"
        self._last_env: dict[str, str] | None = None
        self._last_poll = 0.0
        self._last_second = 0.0
        self._tick_fns: list[Callable[[], None]] = []
        self.on_check_updates: Callable[[], None] | None = None  # set by App
        self.on_install_update: Callable[[], None] | None = None
        self.on_rollback_update: Callable[[], None] | None = None
        self.on_import_settings: Callable[[], None] | None = None
        from firestone_bot import update

        self.previous_version = update.previous_version()  # None from source

        self.ctx = PageContext(
            settings=settings,
            binder=self.binder,
            callbacks={
                "start": self._start,
                "dry_run": self._dry_run,
                "stop": self._stop,
                "is_running": self.is_running,
                "save_now": self.save_now,
                "reload": self._reload,
                "open_log": self.open_log,
                "open_folder": self.open_folder,
                "refresh_status": self.refresh_status,
                "exit": self.request_exit,
                "check_updates": lambda: self.on_check_updates() if self.on_check_updates else None,
                "install_update": lambda: (
                    self.on_install_update() if self.on_install_update else None
                ),
                "rollback_update": lambda: (
                    self.on_rollback_update() if self.on_rollback_update else None
                ),
                "import_settings": lambda: (
                    self.on_import_settings() if self.on_import_settings else None
                ),
            },
            show_page=self.show_page,
            base_dir=self.base_dir,
            register_tick=self._register_tick,
            root=self.root,
            window=self,
            extras={
                "appearance_var": self.appearance_var,
                "settings_existed": os.path.exists(settings.path),
                "previous_version": self.previous_version,
            },
        )

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._set_window_icon()
        self._build_shell(str(self.gui_state.get("page") or "camp"))
        self._bind_keys()
        self._update_bot_widgets()
        self.root.after(150, self._tick)

    # -- construction -------------------------------------------------------------------------
    def _initial_geometry(self) -> str:
        geo = str(self.gui_state.get("geometry") or "")
        m = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geo)
        if m:
            w, h, x, y = int(m[1]), int(m[2]), int(m[3]), int(m[4])
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            if w >= MIN_SIZE[0] and h >= MIN_SIZE[1] and 0 <= x < sw - 100 and 0 <= y < sh - 100:
                return geo
        return DEFAULT_GEOMETRY

    def _register_tick(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._tick_fns.append(callback)

        def unsubscribe() -> None:
            if callback in self._tick_fns:
                self._tick_fns.remove(callback)

        return unsubscribe

    def _build_shell(self, page: str) -> None:
        self.root.configure(fg_color=theme.PAPER)
        self.shell = ctk.CTkFrame(self.root, fg_color=theme.PAPER, corner_radius=0)
        self.shell.grid(row=0, column=0, sticky="nsew")
        self.shell.grid_columnconfigure(0, weight=1)
        self.shell.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_top_banner()
        self.content = ctk.CTkFrame(self.shell, fg_color=theme.PAPER, corner_radius=0)
        self.content.grid(row=2, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._build_commands()
        self._build_status_strip()
        self.pages: dict[str, ctk.CTkBaseClass] = {}
        self.current_page: str | None = None
        self.show_page("camp")
        self.dash = self.ctx.extras["dashboard"]
        if page != "camp":
            self.show_page(page)
        self.dash.set_activity(self.activity_text)
        if self._last_env:
            self.dash.env_result(self._last_env, self._env_footer())
        if self._selftest_inflight:
            self.dash.env_checking()
        self.show_update(self.update_text, self.update_button, self.update_kind)
        self._on_save_state(*self._save_state)
        self._update_bot_widgets()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self.shell, fg_color=theme.HEADER, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(26, 12), pady=20)
        ctk.CTkLabel(
            brand, text="Firestone", text_color=theme.ON_HEADER, font=theme.heading(27)
        ).pack(side="left")
        ctk.CTkLabel(
            brand,
            text=theme.current_skin(),
            text_color=theme.HEADER_MUTED,
            font=theme.heading(17),
        ).pack(side="left", padx=(8, 0))
        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.grid(row=0, column=1, sticky="e", padx=(0, 24), pady=18)
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for index, name in enumerate(PAGE_ORDER):
            button = ctk.CTkButton(
                nav,
                text=PAGE_TITLES[name],
                command=lambda n=name: self.show_page(n),
                fg_color="transparent",
                text_color=theme.ON_HEADER,
                hover_color=theme.ACCENT_HOVER,
                height=36,
                width=78,
                corner_radius=4,
                font=theme.font(13),
            )
            button.grid(row=0, column=index, padx=3)
            self.nav_buttons[name] = button
        self.skin_menu = OptionMenu(
            nav,
            values=list(theme.SKIN_NAMES),
            command=self._select_skin,
            width=150,
            height=36,
            font=theme.font(12),
            fg_color=theme.HEADER,
            button_color=theme.HEADER,
            button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_HEADER,
        )
        self.skin_menu.set(f"Skin: {theme.current_skin()}")
        self.skin_menu.grid(row=0, column=len(PAGE_ORDER), padx=(10, 0))

    def _build_commands(self) -> None:
        dock = ctk.CTkFrame(self.shell, fg_color=theme.SURFACE_ALT, corner_radius=0)
        dock.grid(row=3, column=0, sticky="ew")
        dock.grid_columnconfigure(0, weight=1)
        state = ctk.CTkFrame(dock, fg_color="transparent")
        state.grid(row=0, column=0, sticky="w", padx=26, pady=12)
        self.pill = StatePill(state)
        self.pill.widget.pack(anchor="w")
        ctk.CTkLabel(
            state,
            text="Dry run checks one cycle without sending inputs.",
            text_color=theme.MUTED,
            font=theme.font(11),
        ).pack(anchor="w", pady=(2, 0))
        commands = ctk.CTkFrame(dock, fg_color="transparent")
        commands.grid(row=0, column=1, sticky="e", padx=26, pady=12)
        self.dry_btn = ctk.CTkButton(
            commands,
            text="Dry run",
            command=self._dry_run,
            width=100,
            height=38,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            border_width=1,
            border_color=theme.BORDER,
            hover_color=theme.SURFACE_ALT,
        )
        self.stop_btn = ctk.CTkButton(
            commands,
            text="Stop",
            command=self._stop,
            width=90,
            height=38,
            fg_color=theme.SURFACE,
            text_color=theme.ERR,
            border_width=1,
            border_color=theme.BORDER,
            hover_color=theme.SURFACE_ALT,
        )
        self.start_btn = ctk.CTkButton(
            commands,
            text="Start bot",
            command=self._start,
            width=120,
            height=38,
            fg_color=theme.ACCENT,
            text_color=theme.ON_ACCENT,
            hover_color=theme.ACCENT_HOVER,
        )
        for index, button in enumerate((self.dry_btn, self.stop_btn, self.start_btn)):
            button.grid(row=0, column=index, padx=(8, 0))

    def _select_skin(self, name: str) -> None:
        # Finish the option-menu callback before destroying its menu widget.
        self.root.after_idle(lambda: self.set_skin(name))

    def set_skin(self, name: str) -> None:
        """Rebuild the presentation without touching the runner or live settings."""
        if name not in theme.SKIN_NAMES or name == theme.current_skin() or self._closed:
            return
        page = self.current_page or "camp"
        journal = self.ctx.extras.get("journal")
        if journal:
            journal.capture_state()
        self.shell.destroy()
        self._tick_fns.clear()
        self.binder.release_view()
        for key in ("dashboard", "camp", "automations", "journal", "workshop"):
            self.ctx.extras.pop(key, None)
        theme.set_skin(name)
        self.gui_state["skin"] = name
        self._build_shell(page)
        self._write_state()

    def _set_window_icon(self) -> None:
        """The bot icon (assets/icon.ico + icon-256.png, same image as the exe / .app)."""
        apply_window_icon(self.root)

    def _build_top_banner(self) -> None:
        """Full-width coloured banner below navigation, used for updates."""
        self.top_banner = ctk.CTkFrame(
            self.shell, corner_radius=0, fg_color=theme.BANNER_BG["info"]
        )
        self.top_banner.grid(row=1, column=0, sticky="ew")
        self.top_banner.grid_columnconfigure(1, weight=1)
        self.top_banner_dot = StatusDot(self.top_banner, "info", size=10)
        self.top_banner_dot.widget.grid(row=0, column=0, padx=(16, 0), pady=10)
        self.top_banner_text = ctk.CTkLabel(
            self.top_banner,
            text="",
            anchor="w",
            justify="left",
            font=theme.font(13, "bold"),
            text_color=theme.INFO,
        )
        self.top_banner_text.grid(row=0, column=1, sticky="ew", padx=(8, 12), pady=8)
        self.top_banner_btn = ctk.CTkButton(
            self.top_banner,
            text="Update",
            width=120,
            height=30,
            font=theme.font(13, "bold"),
            command=lambda: self.ctx.call("install_update"),
        )
        self.top_banner_btn.grid(row=0, column=2, padx=(0, 8), pady=6)
        self.top_banner_close = ctk.CTkButton(
            self.top_banner,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            hover=False,
            text_color=theme.MUTED,
            font=theme.font(13),
            command=lambda: self.show_update("", None),
        )
        self.top_banner_close.grid(row=0, column=3, padx=(0, 10), pady=6)
        self.top_banner.grid_remove()

    def _build_status_strip(self) -> None:
        strip = ctk.CTkFrame(self.shell, corner_radius=0, fg_color=theme.PAPER)
        strip.grid(row=4, column=0, sticky="ew")
        strip.grid_columnconfigure(1, weight=1)
        self.strip_dot = StatusDot(strip, "grey")
        self.strip_dot.widget.grid(row=0, column=0, padx=(24, 0), pady=7)
        self.strip_text = ctk.CTkLabel(
            strip, text="Idle", anchor="w", text_color=theme.MUTED, font=theme.font(11)
        )
        self.strip_text.grid(row=0, column=1, sticky="ew", padx=(6, 12), pady=7)
        self.save_label = ctk.CTkLabel(
            strip, text="", anchor="e", text_color=theme.MUTED, font=theme.font(11)
        )
        self.save_label.grid(row=0, column=2, sticky="e", padx=(0, 24), pady=7)
        autowrap(strip, [self.strip_text], offset=310)

    def _bind_keys(self) -> None:
        for i, name in enumerate(PAGE_ORDER, start=1):
            self.root.bind_all(f"<Control-Key-{i}>", lambda _e, n=name: self.show_page(n))
        self.root.bind_all("<Control-s>", lambda _e: self.save_now())
        self.root.bind_all("<F5>", lambda _e: self.refresh_status())
        self.root.bind_all("<Control-q>", lambda _e: self.request_exit())
        self.root.bind_all("<Control-Key-5>", lambda _e: self.skin_menu._open_dropdown_menu())

    # -- pages --------------------------------------------------------------------------------
    def show_page(self, name: str) -> None:
        legacy = name
        name = {
            "dashboard": "camp",
            "main": "automations",
            "town": "automations",
            "guild": "automations",
            "missions": "automations",
            "advanced": "workshop",
            "help": "workshop",
        }.get(name, name)
        if name not in PAGE_ORDER:
            log.warning("unknown page %r", name)
            return
        if name not in self.pages:
            try:
                page = build(name, self.content, self.ctx)
            except Exception as e:
                log.exception("building page %r failed", name)
                messagebox.showerror(
                    "Page failed",
                    f"The {PAGE_TITLES[name]} page could not be built:\n{e}\n\n"
                    "See firestone-bot.log.",
                    parent=self.root,
                )
                return
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()
            self.pages[name] = page
        if self.current_page and self.current_page != name:
            self.pages[self.current_page].grid_remove()
        self.pages[name].grid()
        self.current_page = name
        for n, b in self.nav_buttons.items():
            active = n == name
            b.configure(
                fg_color=theme.SURFACE_ALT if active else "transparent",
                text_color=theme.TEXT if active else theme.ON_HEADER,
                font=theme.font(13, "bold" if active else "normal"),
            )

        if legacy == "help":
            self.ctx.extras["workshop"].open_section("help")
        self.gui_state["page"] = name

    def open_automation(self, group_id: str) -> None:
        self.show_page("automations")
        view = self.ctx.extras.get("automations")
        if view:
            view.open_group(group_id)

    def open_workshop(self, section: str) -> None:
        self.show_page("workshop")
        view = self.ctx.extras.get("workshop")
        if view:
            view.open_section(section)

    # -- appearance ---------------------------------------------------------------------------
    def _apply_appearance(self) -> None:
        mode = self.appearance_var.get().lower()
        if mode in ("system", "light", "dark"):
            ctk.set_appearance_mode(mode)
            self.gui_state["appearance"] = mode

    def set_appearance(self, mode: str) -> None:
        if mode.lower() in ("system", "light", "dark"):
            self.appearance_var.set(mode.capitalize())

    # -- commands -----------------------------------------------------------------------------
    def _start(self) -> None:
        if self.is_running():
            return
        self.binder.flush()
        env = self._last_env or {}
        self.dash.window_banner.set_visible(env.get("window", "").startswith("not found"))
        self.on_start()

    def _dry_run(self) -> None:
        if self.is_running():
            return
        self.binder.flush()
        self.on_dry_run()

    def _stop(self) -> None:
        self.on_stop()

    def save_now(self) -> None:
        self.binder.touch()
        self.binder.flush()

    def _reload(self) -> None:
        if self.binder.dirty and not messagebox.askyesno(
            "Reload settings", "Discard unsaved changes and reload settings.ini?", parent=self.root
        ):
            return
        try:
            self.binder.reload()
        except Exception as e:
            log.exception("reload failed")
            messagebox.showerror("Reload failed", str(e), parent=self.root)

    def open_log(self) -> None:
        self._open(os.path.join(self.base_dir, "firestone-bot.log"))

    def open_folder(self) -> None:
        self._open(self.base_dir)

    @staticmethod
    def _open(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            log.exception("cannot open %s", path)

    # -- thread-safe entry points ---------------------------------------------------------------
    def post_status(self, text: str) -> None:
        self.ui_queue.put(("activity", text))

    def post_call(self, fn: Callable[[], None]) -> None:
        """Run `fn` on the Tk thread (from any thread)."""
        self.ui_queue.put(("call", fn))

    def show_update(self, text: str, button: str | None = None, kind: str = "info") -> None:
        """Top banner (Tk thread): `text` shows it (empty hides it), `button` labels the action
        (None: no button), `kind` picks the colour (info / ok / warn / err)."""
        self.update_text, self.update_button, self.update_kind = text, button, kind
        b = self.top_banner
        if not text:
            if b.winfo_manager():
                b.grid_remove()
            return
        b.configure(fg_color=theme.BANNER_BG.get(kind, theme.BANNER_BG["info"]))
        self.top_banner_dot.set(kind)
        self.top_banner_text.configure(text=text, text_color=theme.colour(kind))
        if button:
            self.top_banner_btn.configure(text=button)
            if not self.top_banner_btn.winfo_manager():
                self.top_banner_btn.grid()
        elif self.top_banner_btn.winfo_manager():
            self.top_banner_btn.grid_remove()
        if not b.winfo_manager():
            b.grid()

    def request_exit(self) -> None:
        if threading.current_thread() is threading.main_thread():
            self._do_exit()  # the close button must not depend on the tick loop
        else:
            self.ui_queue.put(("exit", None))

    _exit = request_exit

    def _append_log(self, line: str) -> None:
        entry = f"{time.strftime('%H:%M:%S')}  {line}"
        was_full = len(self.log_lines) == MAX_LOG_LINES
        self.log_lines.append(entry)
        journal = self.ctx.extras.get("journal")
        if journal:
            journal.append_entry(entry, was_full)

    # -- bot state ------------------------------------------------------------------------------
    def set_bot_state(self, text: str) -> None:
        mapping = {"running": "running", "dry run (no input)": "dry", "stopping...": "stopping"}
        self.bot_state = mapping.get(text, self.bot_state)
        if self.bot_state in ("running", "dry"):
            self.cycle = None
            self.cycle_duration = ""
            self._was_running = True  # so a thread that dies at once is seen as a transition
            # forget the previous run's final line ("Crashed, see log" must not outlive it)
            self.activity_text = "Starting…"
            if hasattr(self, "dash"):
                self.dash.set_activity(self.activity_text)
        self._update_bot_widgets()

    def _update_bot_widgets(self) -> None:
        running = self.is_running()
        text, kind = STATES[self.bot_state]
        self.pill.set(text, kind)
        if hasattr(self, "dash"):
            self.dash.set_state(text, kind, self.cycle, self.cycle_duration)
        start = dry = not running and self.bot_state not in ("running", "dry", "stopping")
        stop = running and self.bot_state != "stopping"
        for b, on in ((self.start_btn, start), (self.dry_btn, dry), (self.stop_btn, stop)):
            state = "normal" if on else "disabled"
            if b.cget("state") != state:
                b.configure(state=state)
        if hasattr(self, "dash"):
            self.dash.set_buttons(start, dry, stop)
        self.strip_dot.set(kind)
        activity = self.activity_text
        strip = text if activity in ("", "Idle", text) else f"{text} · {activity}"
        if self.strip_text.cget("text") != strip:
            self.strip_text.configure(text=strip)

    def _on_activity(self, text: str) -> None:
        self.activity_text = text
        m = re.match(r"Cycle (\d+) done(?: in (\S+?))?(?:,| |$)", text)
        if m:
            self.cycle = int(m[1])
            if m[2]:
                self.cycle_duration = m[2]
        self.dash.set_activity(text)
        if text not in self._recent_logs:
            # Game.status() also logs, so the line normally arrives via the logging bridge;
            # a bare post_status() is mirrored here so the Activity log stays complete.
            self._append_log(text)
        if not self.is_running() and self.bot_state in ("running", "dry", "stopping"):
            terminal = TERMINAL_STATES.get(text)
            if terminal is None and text.startswith("Delay setting"):
                terminal = "delay"
            if terminal:
                self._was_running = False
                self._on_running_changed(False)
                return
        self._update_bot_widgets()

    def _on_running_changed(self, running: bool) -> None:
        if running:
            if self.bot_state not in ("running", "dry", "stopping"):
                self.bot_state = "running"
        else:
            if self.activity_text == "Crashed, see log":
                self.bot_state = "crashed"
            elif self.activity_text.startswith("Delay setting"):
                self.bot_state = "delay"
            else:
                self.bot_state = "stopped"
            self.binder.flush()
            self._last_selftest = 0.0  # re-check the game window soon
        self._update_bot_widgets()

    # -- save indicator -----------------------------------------------------------------------
    def _on_save_state(self, kind: str, text: str) -> None:
        prefix = {"saved": "● ", "deferred": "● ", "error": "! ", "unsaved": "○ "}.get(kind, "")
        self._save_state = (kind, text)
        self.save_label.configure(text=prefix + text, text_color=theme.colour(SAVE_KINDS[kind]))

    def _save_error_dialog(self, error: str) -> None:
        messagebox.showerror(
            "Save failed",
            f"settings.ini could not be written:\n{error}\n\nChanges stay active in memory and "
            "the save is retried on the next change.",
            parent=self.root,
        )

    # -- self-test ------------------------------------------------------------------------------
    def refresh_status(self, manual: bool = True) -> None:
        """Environment check. Manual (F5 / button) checks may restore a minimised game and
        then raise this window; the 30 s auto-refresh only reports."""
        if self._selftest_inflight or self._closed:
            return
        self._selftest_inflight = True
        self._selftest_started = time.monotonic()
        self._selftest_gen += 1
        self._selftest_outstanding += 1
        gen = self._selftest_gen
        self.dash.env_checking()

        def worker():
            try:
                try:
                    result = self.on_self_test(restore=manual)
                except TypeError:  # older callbacks without the keyword
                    result = self.on_self_test()
            except Exception as e:
                log.exception("self-test failed")
                result = {"window": f"self-test failed: {e}"}
            finally:
                capture.close()  # per-thread mss instance: 2 GDI objects per thread otherwise
            self.ui_queue.put(("selftest", (gen, result, manual)))

        threading.Thread(target=worker, name="gui-selftest", daemon=True).start()

    def _env_footer(self) -> str:
        stamp = time.strftime("%H:%M:%S", time.localtime(self._last_selftest))
        mode = (
            "paused while the bot runs"
            if self.is_running()
            else "auto-refresh every 30 s while idle"
        )
        return f"Last checked {stamp} · {mode}"

    def _apply_selftest(self, payload) -> None:
        gen, result, manual = payload
        self._selftest_outstanding = max(0, self._selftest_outstanding - 1)
        if gen != self._selftest_gen:
            log.info("self-test worker %d answered late; ignored", gen)
            return
        self._selftest_inflight = False
        self._last_selftest = time.time()
        self._last_env = dict(result)
        self.dash.env_result(result, self._env_footer())
        if manual and "restored" in result.get("window", "") and self.on_env_restored:
            self.on_env_restored()

    # -- main-thread loop -----------------------------------------------------------------------
    def _tick(self) -> None:
        if self._closed:
            return
        try:
            if self._drain_queue():
                return  # exit requested: the window is gone
            self._poll()
        except Exception:
            log.exception("ui tick failed")
        finally:
            if not self._closed:
                self.root.after(150, self._tick)

    def _drain_queue(self) -> bool:
        """Handle every queued message; True when the exit message was processed."""
        while True:
            try:
                kind, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                return False
            try:
                if kind == "activity":
                    self._on_activity(str(payload))
                elif kind == "log":
                    line = str(payload)
                    self._recent_logs.append(line)
                    self._append_log(line)
                elif kind == "selftest":
                    self._apply_selftest(payload)
                elif kind == "call":  # any callable, run on the Tk thread (update flow)
                    payload()
                elif kind == "exit":
                    self._do_exit()
                    return True
            except Exception:
                log.exception("ui message %r failed", kind)

    def _poll(self) -> None:
        now = time.monotonic()
        if now - self._last_poll >= 0.5:
            self._last_poll = now
            self.binder.refresh_from_settings()
            running = self.is_running()
            stuck = not running and self.bot_state in ("running", "dry", "stopping")
            if running != self._was_running or stuck:
                # `stuck`: the thread died before the first poll saw it alive
                self._was_running = running
                self._on_running_changed(running)
        if now - self._last_second >= 1.0:
            self._last_second = now
            for fn in tuple(self._tick_fns):
                try:
                    fn()
                except Exception:
                    log.exception("tick callback failed")
            if self._selftest_inflight and now - self._selftest_started > SELFTEST_TIMEOUT:
                # The worker is still blocked (find_game_window / grab): its late answer will
                # be ignored. F5 may start a fresh one; auto-refresh waits for it to return.
                self._selftest_inflight = False
                self._last_selftest = time.time()
                log.warning("self-test did not answer within %.0f s", SELFTEST_TIMEOUT)
                self.dash.env_timeout()
            elif (
                not self._selftest_inflight
                and not self._selftest_outstanding
                and not self._was_running
                and time.time() - self._last_selftest >= SELFTEST_PERIOD
            ):
                self.refresh_status(manual=False)
            elif self._last_selftest:
                self.dash.set_env_footer(self._env_footer())

    # -- exit -------------------------------------------------------------------------------------
    def _do_exit(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.on_exit()  # stops the runner and waits for it: no concurrent settings.save()
        except Exception:
            log.exception("on_exit failed")
        try:
            self.binder.flush(force=True)
        except Exception:
            log.exception("flush on exit failed")
        logging.getLogger("firestone_bot").removeHandler(self.log_handler)
        self._write_state()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _write_state(self) -> None:
        try:
            self.gui_state.update(
                geometry=self.root.geometry(),
                page=self.current_page or "camp",
                skin=theme.current_skin(),
                appearance=self.appearance_var.get().lower(),
            )
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.gui_state, f, indent=2)
        except Exception:
            log.exception("cannot write gui_state.json")

    def _prebuild_pages(self) -> None:
        """Build one not-yet-built page per idle slot so navigation is instant later."""
        if self._closed:
            return
        for name in PAGE_ORDER:
            if name not in self.pages:
                try:
                    page = build(name, self.content, self.ctx)
                except Exception:
                    log.exception("prebuilding page %r failed", name)
                    return
                page.grid(row=0, column=0, sticky="nsew")
                page.grid_remove()
                self.pages[name] = page
                self.root.after(200, self._prebuild_pages)
                return

    def run(self) -> None:
        self.root.after(300, self.refresh_status)
        self.root.after(1200, self._prebuild_pages)
        self.root.mainloop()
