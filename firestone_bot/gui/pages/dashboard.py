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
    Banner,
    Meter,
    StatePill,
    StatusDot,
    autowrap,
    register_cleanup,
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


class _CampPanel(ctk.CTkFrame):
    """Compact spacing local to Camp; settings-page cards are unchanged."""

    def __init__(self, parent, title: str) -> None:
        super().__init__(
            parent,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=theme.RADIUS,
        )
        self.grid_columnconfigure(0, weight=1)
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=12, pady=(6, 2))
        ctk.CTkLabel(
            self.header, text=title, height=24, font=theme.heading(19), text_color=theme.TEXT
        ).grid(row=0, column=0, sticky="w")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))


def _note(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        height=16,
        font=theme.font(11),
        text_color=theme.MUTED,
        anchor="w",
        justify="left",
    )


def _metric(parent, column: int, title: str, width: int = 142) -> ctk.CTkLabel:
    block = ctk.CTkFrame(parent, fg_color="transparent", width=width)
    block.grid(row=0, column=column, sticky="ew", padx=(6, 0))
    ctk.CTkLabel(block, text=title, height=18, font=theme.font(12), text_color=theme.MUTED).pack(
        anchor="w"
    )
    value = ctk.CTkLabel(block, text="—", height=26, font=theme.heading(22), text_color=theme.TEXT)
    value.pack(anchor="w")
    return value


class _CompactMeter(Meter):
    """The shared quota behavior in a single row instead of a stacked chart."""

    def __init__(self, parent, label: str) -> None:
        super().__init__(parent, label)
        for child in self.widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                child.configure(height=22, font=theme.font(12))
        self.widget.grid_columnconfigure(0, weight=0, minsize=104)
        self.widget.grid_columnconfigure(1, weight=1)
        self.value.grid_configure(column=2)
        self.bar.configure(width=50, height=5)
        self.bar.grid_configure(row=0, column=1, columnspan=1, padx=10, pady=0)
        if not self._bar_shown:
            self.bar.grid_remove()


class DashboardView:
    """Camp presents real runtime data; the session commands stay in the global dock."""

    def __init__(self, parent, ctx: PageContext) -> None:
        self.ctx = ctx
        # Camp is a single-screen overview; other pages retain their scrollable editors.
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.grid(row=0, column=0, sticky="new", padx=18, pady=8)
        content.grid_columnconfigure(0, weight=1)
        self.sections = {}

        session = self.sections["session"] = _CampPanel(content, "Camp · Session")
        session.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.pill = StatePill(session.header)
        self.pill.widget.grid(row=0, column=1, padx=(10, 0))
        session.header.grid_columnconfigure(2, weight=1)
        self.open_log_btn = ctk.CTkButton(
            session.header,
            text="Read error log",
            command=lambda: ctx.show_page("journal"),
            fg_color=theme.ERR,
            width=105,
            height=26,
        )
        self.open_log_btn.grid(row=0, column=2, sticky="w", padx=10)
        self.open_log_btn.grid_remove()
        for column, (text, command) in enumerate(
            (
                ("Automations →", lambda: ctx.show_page("automations")),
                ("Cycle settings →", lambda: ctx.window.open_workshop("session")),
                ("Journal →", lambda: ctx.show_page("journal")),
            ),
            start=3,
        ):
            ctk.CTkButton(
                session.header,
                text=text,
                command=command,
                width=112,
                height=26,
                fg_color="transparent",
                text_color=theme.TEXT,
                hover_color=theme.SURFACE_ALT,
                font=theme.font(12),
            ).grid(row=0, column=column, padx=(6, 0))
        session.body.grid_columnconfigure(0, weight=1)
        activity = ctk.CTkFrame(session.body, fg_color="transparent")
        activity.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        activity.grid_columnconfigure(0, weight=1)
        self.activity_label = ctk.CTkLabel(
            activity,
            text="Idle",
            anchor="w",
            justify="left",
            height=22,
            wraplength=480,
            text_color=theme.TEXT,
            font=theme.font(16, "bold"),
        )
        self.activity_label.grid(row=0, column=0, sticky="ew")
        autowrap(activity, [self.activity_label], offset=4)
        self.cycle_label = _metric(session.body, 1, "Last completed cycle")
        self.cycle_value = _metric(session.body, 2, "Last cycle duration")
        self.window_banner = Banner(session.body, "warn", WINDOW_MISSING)
        self.window_banner.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.window_banner.label.grid_configure(padx=8, pady=3)
        self.window_banner.label.configure(height=18)
        autowrap(session.body, [self.window_banner.label], offset=20)
        self.window_banner.set_visible(False)

        details = ctk.CTkFrame(content, fg_color="transparent")
        details.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        details.grid_columnconfigure(0, weight=3, uniform="camp_details")
        details.grid_columnconfigure(1, weight=2, uniform="camp_details")
        environment = self.sections["environment"] = _CampPanel(details, "Game checks")
        environment.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        environment.header.grid_columnconfigure(1, weight=1)
        self.recheck_btn = ctk.CTkButton(
            environment.header,
            text="Re-check (F5)",
            command=lambda: ctx.call("refresh_status"),
            width=105,
            height=26,
            font=theme.font(12),
        )
        self.recheck_btn.grid(row=0, column=1, sticky="e")
        grid = environment.body
        grid.grid_columnconfigure(2, weight=1)
        self.env_dots: dict[str, StatusDot] = {}
        self.env_values: dict[str, ctk.CTkLabel] = {}
        for i, (key, label) in enumerate(ENV_ROWS):
            dot = StatusDot(grid, "grey", size=12)
            dot.widget.configure(height=18)
            dot.widget.grid(row=i, column=0, sticky="w")
            ctk.CTkLabel(
                grid, text=label, anchor="w", width=76, height=18, font=theme.font(12)
            ).grid(row=i, column=1, sticky="w", padx=(4, 8))
            value = ctk.CTkLabel(
                grid,
                text="Not checked",
                anchor="w",
                justify="left",
                height=18,
                wraplength=385,
                text_color=theme.MUTED,
                font=theme.font(12),
            )
            value.grid(row=i, column=2, sticky="ew")
            self.env_dots[key], self.env_values[key] = dot, value
        autowrap(grid, list(self.env_values.values()), offset=108)
        self.env_footer = _note(grid, "Not checked yet")
        self.env_footer.grid(row=len(ENV_ROWS), column=0, columnspan=3, sticky="ew", pady=(6, 0))
        autowrap(grid, [self.env_footer], offset=4)

        today = self.sections["today"] = _CampPanel(details, "Daily limits")
        today.grid(row=0, column=1, sticky="nsew")
        today.body.grid_columnconfigure(0, weight=1)
        for i, (name, label) in enumerate(
            (
                ("meter_tokens", "Tavern tokens"),
                ("meter_chaos", "Chaos hits"),
                ("meter_scarab", "Scarab plays"),
                ("meter_crystal", "Crystal hits"),
            )
        ):
            meter = _CompactMeter(today.body, label)
            meter.widget.grid(row=i, column=0, sticky="ew", pady=2)
            setattr(self, name, meter)
        arena = ctk.CTkFrame(today.body, fg_color="transparent")
        arena.grid(row=4, column=0, sticky="ew", pady=(2, 0))
        arena.grid_columnconfigure(1, weight=1)
        self.arena_dot = StatusDot(arena, "grey", size=12)
        self.arena_dot.widget.configure(height=22)
        self.arena_dot.widget.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(arena, text="Arena", anchor="w", height=22, font=theme.font(12)).grid(
            row=0, column=1, sticky="w", padx=(4, 0)
        )
        self.arena_value = ctk.CTkLabel(
            arena,
            text="Pending",
            anchor="e",
            height=22,
            text_color=theme.MUTED,
            font=theme.font(12),
        )
        self.arena_value.grid(row=0, column=2, sticky="e")
        self.reset_label = _note(today.body, "Last daily reset: not detected yet")
        self.reset_label.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        autowrap(today.body, [self.reset_label], offset=4)

        totals = ctk.CTkFrame(content, fg_color="transparent")
        totals.grid(row=2, column=0, sticky="ew")
        totals.grid_columnconfigure(0, weight=1, uniform="camp_totals")
        totals.grid_columnconfigure(1, weight=2, uniform="camp_totals")
        account = self.sections["account"] = _CampPanel(totals, "Account & guild")
        account.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.level_values = {}
        for i, (key, label) in enumerate(
            (("account_level", "Account level"), ("guild_level", "Guild level"))
        ):
            account.body.grid_columnconfigure(i, weight=1, uniform="levels")
            self.level_values[key] = _metric(account.body, i, label, width=80)
        explanation = _note(account.body, "Read during visits; — means not read yet.")
        explanation.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        autowrap(account.body, [explanation], offset=4)
        statistics = self.sections["statistics"] = _CampPanel(totals, "All-time cycle statistics")
        statistics.grid(row=0, column=1, sticky="nsew")
        self.stat_values = {}
        for index, (key, label) in enumerate(
            (
                ("cycles", "Completed cycles"),
                ("last", "Last cycle"),
                ("average", "Average cycle"),
                ("total", "Total cycle time"),
            )
        ):
            statistics.body.grid_columnconfigure(index, weight=1, uniform="statistics")
            self.stat_values[key] = _metric(statistics.body, index, label, width=100)
        _note(statistics.body, "Recorded by the bot; saved between launches.").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(4, 0)
        )
        self.refresh_today()
        unsubscribe = ctx.register_tick(self.refresh_today)
        if unsubscribe:
            register_cleanup(self.frame, unsubscribe)

    # -- state ------------------------------------------------------------------------------
    def set_state(self, text: str, kind: str, cycle: int | None, duration: str = "") -> None:
        self.pill.set(text, kind)
        c = str(cycle) if cycle is not None else "—"
        if self.cycle_label.cget("text") != c:
            self.cycle_label.configure(text=c)
        # Session duration falls back to the last cycle saved by the runner.
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
