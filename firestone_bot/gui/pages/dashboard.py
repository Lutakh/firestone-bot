"""Dashboard: control, environment (self-test), today's counters and the activity log.

Non-scrolling page; the view object is stored in `ctx.extras["dashboard"]` so the window can
push state into it from `_tick`.
"""

from __future__ import annotations

import time
from collections import deque

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui import theme
from firestone_bot.gui.catalog import format_ahk_stamp
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import Card, LinkButton, Meter, StatePill, StatusDot, autowrap

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
    def __init__(self, parent, ctx: PageContext) -> None:
        self.ctx = ctx
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        f = self.frame
        f.grid_columnconfigure(0, weight=3, uniform="top")
        f.grid_columnconfigure(1, weight=4, uniform="top")
        f.grid_columnconfigure(2, weight=3, uniform="top")
        f.grid_rowconfigure(1, weight=1)
        pad = {"padx": (24, 0), "pady": (16, 0)}

        # -- Control ---------------------------------------------------------------------
        control = Card(f, ctx, "Control")
        control.grid(row=0, column=0, sticky="nsew", **pad)
        btns = ctk.CTkFrame(control.body, fg_color="transparent")
        self.start_btn = ctk.CTkButton(
            btns,
            text="START",
            command=lambda: ctx.call("start"),
            fg_color=theme.OK,
            hover_color=("#177a42", "#2fb86c"),
            height=36,
            width=60,
            font=theme.font(12, "bold"),
        )
        self.dry_btn = ctk.CTkButton(
            btns,
            text="DRY RUN",
            command=lambda: ctx.call("dry_run"),
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            height=36,
            width=60,
            font=theme.font(12, "bold"),
        )
        self.stop_btn = ctk.CTkButton(
            btns,
            text="STOP",
            command=lambda: ctx.call("stop"),
            fg_color=theme.ERR,
            hover_color=("#96261c", "#e05252"),
            height=36,
            width=60,
            font=theme.font(12, "bold"),
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.stop_btn.grid(row=0, column=1, sticky="ew")
        self.dry_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        btns.grid_columnconfigure(0, weight=1, uniform="ctl")
        btns.grid_columnconfigure(1, weight=1, uniform="ctl")
        control.add(btns, always_enabled=True)
        state_row = ctk.CTkFrame(control.body, fg_color="transparent")
        self.pill = StatePill(state_row)
        self.pill.widget.pack(side="left")
        self.cycle_label = ctk.CTkLabel(
            state_row, text="", text_color=theme.MUTED, font=theme.font(12)
        )
        self.cycle_label.pack(side="left", padx=(10, 0))
        control.add(state_row, always_enabled=True, pady=(8, 2))
        # self-update banner (hidden until App finds a newer release)
        self.update_row = ctk.CTkFrame(control.body, fg_color="transparent")
        self.update_label = ctk.CTkLabel(
            self.update_row,
            text="",
            anchor="w",
            justify="left",
            wraplength=250,
            font=theme.font(12),
        )
        self.update_label.pack(side="top", anchor="w")
        self.update_btn = ctk.CTkButton(
            self.update_row,
            text="Update",
            command=lambda: ctx.call("install_update"),
            height=28,
            width=90,
            font=theme.font(12, "bold"),
        )
        control.add(self.update_row, always_enabled=True, pady=(2, 2))
        self.update_row.grid_remove()
        self.activity_label = ctk.CTkLabel(
            control.body,
            text="Idle",
            anchor="w",
            justify="left",
            wraplength=250,
            font=theme.font(13),
        )
        control.add(self.activity_label, always_enabled=True, pady=(2, 6))
        self.window_banner = control.banner("warn", WINDOW_MISSING, visible=False)
        self.open_log_btn = ctk.CTkButton(
            control.body,
            text="Open log file",
            command=lambda: ctx.call("open_log"),
            fg_color=theme.ERR,
            height=30,
            width=120,
        )
        control.add(self.open_log_btn, always_enabled=True, pady=(2, 4))
        self.open_log_btn.grid_remove()
        note1 = control.note(
            "Dry run runs one full cycle with mouse and keyboard disabled and logs every probe "
            "and click.",
            wrap=250,
        )
        control.note("Exit hotkey: Win+Esc", wrap=250)
        autowrap(control.body, [self.activity_label, note1, self.window_banner.label], offset=8)

        # -- Environment -----------------------------------------------------------------
        env = Card(f, ctx, "Environment")
        env.grid(row=0, column=1, sticky="nsew", **pad)
        grid = ctk.CTkFrame(env.body, fg_color="transparent")
        grid.grid_columnconfigure(2, weight=1)
        self.env_dots: dict[str, StatusDot] = {}
        self.env_values: dict[str, ctk.CTkLabel] = {}
        for i, (key, label) in enumerate(ENV_ROWS):
            dot = StatusDot(grid, "grey")
            dot.widget.grid(row=i, column=0, sticky="w")
            ctk.CTkLabel(grid, text=label, anchor="w", font=theme.font(13), width=92).grid(
                row=i, column=1, sticky="w", padx=(4, 8)
            )
            val = ctk.CTkLabel(
                grid,
                text="checking…",
                anchor="w",
                justify="left",
                wraplength=230,
                text_color=theme.MUTED,
                font=theme.font(12),
            )
            val.grid(row=i, column=2, sticky="w", pady=1)
            self.env_dots[key] = dot
            self.env_values[key] = val
        env.add(grid, always_enabled=True)
        autowrap(grid, list(self.env_values.values()), offset=130)
        foot = ctk.CTkFrame(env.body, fg_color="transparent")
        foot.grid_columnconfigure(0, weight=1)
        self.env_footer = ctk.CTkLabel(
            foot,
            text="Not checked yet",
            anchor="w",
            justify="left",
            wraplength=210,
            text_color=theme.MUTED,
            font=theme.font(12),
        )
        self.env_footer.grid(row=0, column=0, sticky="w")
        self.recheck_btn = ctk.CTkButton(
            foot,
            text="Re-check (F5)",
            command=lambda: ctx.call("refresh_status"),
            height=28,
            width=110,
        )
        self.recheck_btn.grid(row=0, column=1, sticky="e", padx=(8, 0))
        env.add(foot, always_enabled=True, pady=(8, 2))
        autowrap(foot, [self.env_footer], offset=130)

        # -- Today -----------------------------------------------------------------------
        today = Card(f, ctx, "Today")
        today.grid(row=0, column=2, sticky="nsew", padx=(24, 24), pady=(16, 0))
        self.meter_tokens = today.add(Meter(today.body, "Tavern tokens"), pady=(2, 6))
        self.meter_chaos = today.add(Meter(today.body, "Chaos hits"), pady=(2, 6))
        self.meter_scarab = today.add(Meter(today.body, "Scarab plays"), pady=(2, 6))
        self.meter_crystal = today.add(Meter(today.body, "Crystal hits"), pady=(2, 6))
        cyc = ctk.CTkFrame(today.body, fg_color="transparent")
        ctk.CTkLabel(cyc, text="Last cycle", anchor="w", font=theme.font(13)).pack(side="left")
        self.cycle_value = ctk.CTkLabel(
            cyc, text="-", anchor="e", font=theme.font(13, "bold"), text_color=theme.MUTED
        )
        self.cycle_value.pack(side="right")
        today.add(cyc, pady=(2, 6), always_enabled=True)
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
        today.add(arena, pady=(2, 6))
        self.reset_label = today.note("Last daily reset: not detected yet", wrap=230)
        note2 = today.note(
            "Counters reset when the daily shop's free box is claimable again.", wrap=230
        )
        autowrap(today.body, [self.reset_label, note2], offset=8)
        today.add(LinkButton(today.body, "Edit limits", lambda: ctx.show_page("town")), pady=(2, 0))

        # -- Activity --------------------------------------------------------------------
        act = Card(f, ctx, "Activity", expand=True)
        act.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=24, pady=(16, 16))
        bar = ctk.CTkFrame(act.body, fg_color="transparent")
        for text, cmd in (
            ("Clear", self.clear_log),
            ("Copy all", self.copy_log),
            ("Open log file", lambda: ctx.call("open_log")),
        ):
            ctk.CTkButton(bar, text=text, command=cmd, height=26, width=90).pack(
                side="left", padx=(0, 6)
            )
        self.follow_btn = ctk.CTkButton(
            bar, text="↓ Follow", command=self.follow, height=26, width=80, fg_color=theme.INFO
        )
        self.follow_btn.pack(side="left", padx=(0, 6))
        self.follow_btn.pack_forget()
        self.count_label = ctk.CTkLabel(
            bar, text="0 lines", text_color=theme.MUTED, font=theme.font(12)
        )
        self.count_label.pack(side="right")
        act.add(bar, always_enabled=True, pady=(0, 4))
        self.textbox = ctk.CTkTextbox(
            act.body,
            font=ctk.CTkFont(family=theme.MONO_FAMILY, size=11),
            wrap="none",
            height=220,
            state="disabled",
        )
        act.add(self.textbox, always_enabled=True, expand=True, pady=(0, 0))
        self._lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._placeholder = True
        self._set_text("Nothing yet. Press START or DRY RUN.")
        self._detached = False

        self.refresh_today()
        ctx.register_tick(self.refresh_today)

    def show_update(self, text: str, button: str | None = None) -> None:
        """Show the update banner with `text`; `button` labels the action (None hides it)."""
        self.update_label.configure(text=text)
        if button:
            self.update_btn.configure(text=button)
            if not self.update_btn.winfo_manager():
                self.update_btn.pack(side="top", anchor="w", pady=(4, 0))
        elif self.update_btn.winfo_manager():
            self.update_btn.pack_forget()
        if text and not self.update_row.winfo_manager():
            self.update_row.grid()
        elif not text and self.update_row.winfo_manager():
            self.update_row.grid_remove()

    # -- state ------------------------------------------------------------------------------
    def set_state(self, text: str, kind: str, cycle: int | None, duration: str = "") -> None:
        self.pill.set(text, kind)
        c = f"cycle {cycle}" if cycle else ""
        if self.cycle_label.cget("text") != c:
            self.cycle_label.configure(text=c)
        # the duration lives in the Today card, readable whatever the window size
        d = f"{duration} (cycle {cycle})" if duration and cycle else duration or "-"
        if self.cycle_value.cget("text") != d:
            self.cycle_value.configure(text=d)
        crashed = kind == "err"
        if crashed and not self.open_log_btn.winfo_manager():
            self.open_log_btn.grid()
        elif not crashed and self.open_log_btn.winfo_manager():
            self.open_log_btn.grid_remove()

    def set_buttons(self, start: bool, dry: bool, stop: bool) -> None:
        for b, on in ((self.start_btn, start), (self.dry_btn, dry), (self.stop_btn, stop)):
            state = "normal" if on else "disabled"
            if b.cget("state") != state:
                b.configure(state=state)

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
        self.meter_tokens.set(daily._int(s, "TokenCountDaily"), daily._int(s, "MaxTokens"))
        self.meter_chaos.set(daily._int(s, "ChaosCountDaily"), daily._int(s, "MaxChaos"))
        self.meter_scarab.set(daily._int(s, "ScarabCountDaily"), daily._int(s, "MaxScarab"))
        self.meter_crystal.set(daily._int(s, "CrystalCountDaily"), daily._int(s, "MaxCrystals"))
        done = daily.arena_done(s)
        self.arena_dot.set("ok" if done else "grey")
        text = "Done" if done else "Pending"
        if self.arena_value.cget("text") != text:
            self.arena_value.configure(text=text, text_color=theme.OK if done else theme.MUTED)
        reset = format_ahk_stamp(s.get("LastTokenReset"), "not detected yet")
        text = f"Last daily reset: {reset}"
        if self.reset_label.cget("text") != text:
            self.reset_label.configure(text=text)

    # -- log --------------------------------------------------------------------------------
    def _set_text(self, text: str) -> None:
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", text)
        self.textbox.configure(state="disabled")

    def append_log(self, line: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        entry = f"{stamp}  {line}"
        if self._placeholder:
            self._placeholder = False
            self._set_text("")
        at_end = self.textbox.yview()[1] >= 0.999
        self._lines.append(entry)
        self.textbox.configure(state="normal")
        if len(self._lines) == MAX_LOG_LINES:
            self.textbox.delete("1.0", "2.0")
        self.textbox.insert("end", entry + "\n")
        self.textbox.configure(state="disabled")
        if at_end and not self._detached:
            self.textbox.see("end")
        else:
            self._detached = True
            if not self.follow_btn.winfo_manager():
                self.follow_btn.pack(side="left", padx=(0, 6))
        self.count_label.configure(text=f"{len(self._lines)} lines")

    def follow(self) -> None:
        self._detached = False
        self.textbox.see("end")
        self.follow_btn.pack_forget()

    def clear_log(self) -> None:
        self._lines.clear()
        self._placeholder = True
        self._set_text("Nothing yet. Press START or DRY RUN.")
        self.count_label.configure(text="0 lines")
        self.follow()

    def copy_log(self) -> None:
        self.textbox.clipboard_clear()
        self.textbox.clipboard_append("\n".join(self._lines))


def build(parent, ctx: PageContext):
    view = DashboardView(parent, ctx)
    ctx.extras["dashboard"] = view
    return view.frame
