"""Camp: actual session state, environment checks, daily counters and known levels.

The view object is stored in `ctx.extras["dashboard"]` so the window can
push state into it from `_tick`.
"""

from __future__ import annotations

import os

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui import theme
from firestone_bot.gui.catalog import format_ahk_stamp
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import (
    Card,
    Meter,
    StatePill,
    StatusDot,
    autowrap,
    page_frame,
    page_title,
)
from firestone_bot.stats import average_cycle_ms, cycles_total, fmt_ms

ENV_ROWS = [
    ("window", "Game window"),
    ("platform", "Platform"),
    ("client", "Client area"),
    ("scale", "Scale"),
    ("dpi", "DPI"),
    ("capture", "Capture"),
    ("input", "Input"),
]
MAX_LOG_LINES = 2000
WINDOW_MISSING = "Game window not found. Start Firestone (Steam or Epic), maximized, then Re-check."


def env_kind(key: str, value: str) -> str:
    """Colour rule of one Environment row (spec 10.1)."""
    v = value.strip()
    if v in ("-", ""):
        return "grey"
    if key == "window":
        return (
            "err"
            if v.startswith(("not found", "self-test failed", "macOS permission missing"))
            else "ok"
        )
    if key == "platform":
        return "ok" if v.lower() in ("steam", "epic") else "warn"
    if key == "scale":
        return "warn" if "differs" in v else "ok" if "aspect OK" in v else "grey"
    if key == "capture":
        return "err" if v.startswith("FAILED") else "ok" if v.startswith("OK") else "grey"
    if key == "input":
        return "grey"
    return "ok"


class DashboardView:
    """Camp presents real runtime data; the session commands stay in the global dock."""

    def __init__(self, parent, ctx: PageContext) -> None:
        self.ctx = ctx
        self.frame, content = page_frame(parent)
        page_title(
            content,
            "A quiet place to run your bot.",
            "Your session, game checks and daily limits, together at camp.",
        )
        columns = ctk.CTkFrame(content, fg_color="transparent")
        columns.pack(fill="both", expand=True, pady=(6, 20))
        columns.grid_columnconfigure(0, weight=3, uniform="camp")
        columns.grid_columnconfigure(1, weight=2, uniform="camp")

        session = Card(columns, ctx, "Session")
        session.grid(row=0, column=0, sticky="nsew", padx=(0, 18), pady=(0, 18))
        self.pill = StatePill(session.body)
        session.add(self.pill.widget, always_enabled=True)
        self.pill.widget.grid_configure(sticky="w")
        self.activity_label = ctk.CTkLabel(
            session.body,
            text="Idle",
            anchor="w",
            justify="left",
            wraplength=430,
            text_color=theme.TEXT,
            font=theme.heading(25),
        )
        session.add(self.activity_label, always_enabled=True, pady=(14, 18))
        data = ctk.CTkFrame(session.body, fg_color="transparent")
        data.grid_columnconfigure((0, 1), weight=1, uniform="cycle")
        ctk.CTkLabel(
            data,
            text="Last completed cycle",
            anchor="w",
            text_color=theme.MUTED,
            font=theme.font(12),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            data,
            text="Last cycle duration",
            anchor="w",
            text_color=theme.MUTED,
            font=theme.font(12),
        ).grid(row=0, column=1, sticky="w")
        self.cycle_label = ctk.CTkLabel(data, text="—", anchor="w", font=theme.heading(28))
        self.cycle_label.grid(row=1, column=0, sticky="w", pady=(2, 12))
        self.cycle_value = ctk.CTkLabel(data, text="—", anchor="w", font=theme.heading(28))
        self.cycle_value.grid(row=1, column=1, sticky="w", pady=(2, 12))
        session.add(data, always_enabled=True)
        self.window_banner = session.banner("warn", WINDOW_MISSING, visible=False)
        self.open_log_btn = ctk.CTkButton(
            session.body,
            text="Read the error log",
            command=lambda: ctx.show_page("journal"),
            fg_color=theme.ERR,
            height=32,
        )
        session.add(self.open_log_btn, always_enabled=True)
        self.open_log_btn.grid_remove()
        note = session.note("Choose Start bot or Dry run in the session bar below.")
        autowrap(session.body, [self.activity_label, note, self.window_banner.label], offset=8)
        for text, command in (
            ("Review automations  →", lambda: ctx.show_page("automations")),
            ("Adjust the pause between cycles  →", lambda: ctx.window.open_workshop("session")),
            ("Read the activity journal  →", lambda: ctx.show_page("journal")),
        ):
            button = ctk.CTkButton(
                session.body,
                text=text,
                command=command,
                anchor="w",
                height=36,
                fg_color="transparent",
                text_color=theme.TEXT,
                hover_color=theme.SURFACE_ALT,
                font=theme.font(13),
            )
            session.add(button, always_enabled=True, pady=(3, 0))

        today = Card(columns, ctx, "Daily limits")
        today.grid(row=0, column=1, sticky="nsew", pady=(0, 18))
        self.meter_tokens = today.add(Meter(today.body, "Tavern tokens"), pady=(2, 8))
        self.meter_chaos = today.add(Meter(today.body, "Chaos hits"), pady=(2, 8))
        self.meter_scarab = today.add(Meter(today.body, "Scarab plays"), pady=(2, 8))
        self.meter_crystal = today.add(Meter(today.body, "Crystal hits"), pady=(2, 8))
        arena = ctk.CTkFrame(today.body, fg_color="transparent")
        arena.grid_columnconfigure(1, weight=1)
        self.arena_dot = StatusDot(arena, "grey")
        self.arena_dot.widget.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(arena, text="Arena", anchor="w", font=theme.font(13)).grid(
            row=0, column=1, sticky="w", padx=(4, 0)
        )
        self.arena_value = ctk.CTkLabel(
            arena, text="Pending", anchor="e", text_color=theme.MUTED, font=theme.font(12)
        )
        self.arena_value.grid(row=0, column=2, sticky="e")
        today.add(arena, always_enabled=True)
        self.reset_label = today.note("Last daily reset: not detected yet", wrap=300)
        autowrap(today.body, [self.reset_label], offset=8)

        environment = Card(columns, ctx, "Game checks")
        environment.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        grid = ctk.CTkFrame(environment.body, fg_color="transparent")
        grid.grid_columnconfigure(2, weight=1)
        self.env_dots: dict[str, StatusDot] = {}
        self.env_values: dict[str, ctk.CTkLabel] = {}
        for i, (key, label) in enumerate(ENV_ROWS):
            dot = StatusDot(grid, "grey")
            dot.widget.grid(row=i, column=0, sticky="w")
            ctk.CTkLabel(grid, text=label, anchor="w", width=92, font=theme.font(12)).grid(
                row=i, column=1, sticky="w", padx=(4, 8)
            )
            value = ctk.CTkLabel(
                grid,
                text="Not checked",
                anchor="w",
                justify="left",
                wraplength=270,
                text_color=theme.MUTED,
                font=theme.font(12),
            )
            value.grid(row=i, column=2, sticky="ew", pady=2)
            self.env_dots[key], self.env_values[key] = dot, value
        environment.add(grid, always_enabled=True)
        autowrap(grid, list(self.env_values.values()), offset=130)
        self.env_footer = environment.note("Not checked yet", wrap=420)
        autowrap(environment.body, [self.env_footer], offset=8)
        (self.recheck_btn,) = environment.buttons(
            ("Re-check environment (F5)", lambda: ctx.call("refresh_status"))
        )

        account = Card(columns, ctx, "Account & guild")
        account.grid(row=1, column=1, sticky="nsew")
        self.level_values = {}
        for key, label in (("account_level", "Account level"), ("guild_level", "Guild level")):
            row = ctk.CTkFrame(account.body, fg_color="transparent")
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=label, anchor="w", font=theme.font(13)).grid(
                row=0, column=0, sticky="w"
            )
            self.level_values[key] = ctk.CTkLabel(row, text="—", font=theme.heading(22))
            self.level_values[key].grid(row=0, column=1, sticky="e")
            account.add(row, always_enabled=True, pady=(5, 10))
        explanation = account.note(
            "Levels are read by the bot during visits. Unread levels stay blank.", wrap=300
        )
        autowrap(account.body, [explanation], offset=8)
        account.buttons(("Files & application", lambda: ctx.window.open_workshop("files")))
        statistics = Card(columns, ctx, "All-time cycle statistics")
        statistics.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        grid = ctk.CTkFrame(statistics.body, fg_color="transparent")
        self.stat_values = {}
        for index, (key, label) in enumerate(
            (
                ("cycles", "Completed cycles"),
                ("last", "Last cycle"),
                ("average", "Average cycle"),
                ("total", "Total time in cycles"),
            )
        ):
            grid.grid_columnconfigure(index, weight=1, uniform="statistics")
            ctk.CTkLabel(grid, text=label, text_color=theme.MUTED, font=theme.font(12)).grid(
                row=0, column=index, sticky="w", padx=(0, 12)
            )
            self.stat_values[key] = ctk.CTkLabel(grid, text="—", font=theme.heading(24))
            self.stat_values[key].grid(row=1, column=index, sticky="w", padx=(0, 12))
        statistics.add(grid, always_enabled=True)
        statistics.note("Recorded by the bot and retained between launches.")
        self.refresh_today()
        unsubscribe = ctx.register_tick(self.refresh_today)
        if unsubscribe:
            self.frame.bind(
                "<Destroy>", lambda e: unsubscribe() if e.widget is self.frame else None, add="+"
            )

    # -- state ------------------------------------------------------------------------------
    def set_state(self, text: str, kind: str, cycle: int | None, duration: str = "") -> None:
        self.pill.set(text, kind)
        c = str(cycle) if cycle is not None else "—"
        if self.cycle_label.cget("text") != c:
            self.cycle_label.configure(text=c)
        # the duration lives in the Today card, readable whatever the window size
        d = duration or fmt_ms(self.ctx.settings.get("LastCycleMs"))
        if self.cycle_value.cget("text") != d:
            self.cycle_value.configure(text=d)
        crashed = kind == "err"
        if crashed and not self.open_log_btn.winfo_manager():
            self.open_log_btn.grid()
        elif not crashed and self.open_log_btn.winfo_manager():
            self.open_log_btn.grid_remove()

    def set_buttons(self, start: bool, dry: bool, stop: bool) -> None:
        """The global session bar owns these commands in every page."""

    def set_activity(self, text: str) -> None:
        if self.activity_label.cget("text") != text:
            self.activity_label.configure(text=text)

    # -- environment ------------------------------------------------------------------------
    def env_checking(self) -> None:
        for key, _ in ENV_ROWS:
            self.env_dots[key].set("grey")
            self.env_values[key].configure(text="checking…", text_color=theme.MUTED)
        self.recheck_btn.configure(state="disabled")

    def env_result(self, result: dict[str, str], footer: str) -> None:
        for key, _ in ENV_ROWS:
            value = result.get(key, "-")
            kind = env_kind(key, value)
            self.env_dots[key].set(kind)
            self.env_values[key].configure(
                text=value, text_color=theme.colour(kind) if kind != "grey" else theme.MUTED
            )
        window = result.get("window", "")
        self.window_banner.set_visible(window.startswith(("not found", "self-test failed")))
        self.env_footer.configure(text=footer)
        self.recheck_btn.configure(state="normal")

    def env_timeout(self) -> None:
        for key, _ in ENV_ROWS:
            self.env_dots[key].set("warn")
            self.env_values[key].configure(text="no answer (check the log)", text_color=theme.WARN)
        self.recheck_btn.configure(state="normal")

    def set_env_footer(self, text: str) -> None:
        if self.env_footer.cget("text") != text:
            self.env_footer.configure(text=text)

    # -- today --------------------------------------------------------------------------------
    def refresh_today(self) -> None:
        s = self.ctx.settings
        progress = _load_progress(os.path.join(self.ctx.base_dir, "progress.json"))
        self.meter_tokens.set(daily._int(s, "TokenCountDaily"), daily._int(s, "MaxTokens"))
        for meter, feature, used, limit in (
            (self.meter_chaos, "guild_chaos", "ChaosCountDaily", "MaxChaos"),
            (self.meter_scarab, "scarab", "ScarabCountDaily", "MaxScarab"),
            (self.meter_crystal, "guild_crystal", "CrystalCountDaily", "MaxCrystals"),
        ):
            reason = progress.locked_short(feature)
            if reason:
                meter.set_locked(reason)  # "0 / 10" on a locked feature only frustrates
            else:
                meter.set(daily._int(s, used), daily._int(s, limit))
        reason = progress.locked_short("arena")
        done = daily.arena_done(s) and not reason
        self.arena_dot.set("ok" if done else "grey")
        text = f"Locked ({reason})" if reason else "Done" if done else "Pending"
        if self.arena_value.cget("text") != text:
            self.arena_value.configure(text=text, text_color=theme.OK if done else theme.MUTED)
        for key, label in self.level_values.items():
            value = getattr(progress, key)
            text = "-" if value is None else str(value)
            if label.cget("text") != text:
                label.configure(text=text)
        reset = format_ahk_stamp(s.get("LastTokenReset"), "not detected yet")
        for key, value in (
            ("cycles", str(cycles_total(s))),
            ("last", fmt_ms(s.get("LastCycleMs"))),
            ("average", fmt_ms(average_cycle_ms(s))),
            ("total", fmt_ms(s.get("CycleMsTotal"))),
        ):
            if self.stat_values[key].cget("text") != value:
                self.stat_values[key].configure(text=value)
        text = f"Last daily reset: {reset}"
        if self.reset_label.cget("text") != text:
            self.reset_label.configure(text=text)

    @property
    def _lines(self):
        """Compatibility for consumers of the former dashboard log buffer."""
        return self.ctx.window.log_lines


def build(parent, ctx: PageContext):
    view = DashboardView(parent, ctx)
    ctx.extras["dashboard"] = ctx.extras["camp"] = view
    return view.frame


def _load_progress(path: str):
    """Account and guild levels reported by the runner, empty until observed."""
    from firestone_bot.progress import Progress

    return Progress.load(path)
