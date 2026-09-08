"""Dashboard: control, environment (self-test), today's counters and the activity log.

Non-scrolling page; the view object is stored in `ctx.extras["dashboard"]` so the window can
push state into it from `_tick`.
"""

from __future__ import annotations

import os
import time
from collections import deque

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui import theme
from firestone_bot.gui.catalog import format_ahk_stamp
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.routines import ROUTINES, enabled_count
from firestone_bot.gui.widgets import (
    Card,
    LinkButton,
    Meter,
    StatusDot,
    autowrap,
    bind_platform_wheel,
    stabilize_textbox,
)

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
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)
        self.tabs = ctk.CTkTabview(self.frame, fg_color="transparent", border_width=0)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=12, pady=(0, 10))
        for name in ("Routines", "Diagnostics", "Journal"):
            tab = self.tabs.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
        overview = ctk.CTkScrollableFrame(self.tabs.tab("Routines"), fg_color="transparent")
        overview.grid(row=0, column=0, sticky="nsew")
        overview.grid_columnconfigure(0, weight=1)
        bind_platform_wheel(overview)
        self._build_routines(overview)
        f = ctk.CTkScrollableFrame(self.tabs.tab("Diagnostics"), fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        bind_platform_wheel(f)
        f.grid_columnconfigure(0, weight=1)
        # Session controls belong to the window, so they stay visible on every page.
        for name in (
            "start_btn",
            "dry_btn",
            "stop_btn",
            "pill",
            "cycle_label",
            "activity_label",
            "window_banner",
            "open_log_btn",
        ):
            setattr(self, name, getattr(ctx.window.session, name))

        # -- Environment -----------------------------------------------------------------
        env = Card(f, ctx, "Environment")
        env.grid(row=0, column=0, sticky="nsew", padx=4, pady=(8, 12))
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
        today.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 12))
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
        self.level_values = {}
        for key, label in (("account_level", "Account level"), ("guild_level", "Guild level")):
            lvl = ctk.CTkFrame(today.body, fg_color="transparent")
            ctk.CTkLabel(lvl, text=label, anchor="w", font=theme.font(13)).pack(side="left")
            self.level_values[key] = ctk.CTkLabel(
                lvl, text="-", anchor="e", font=theme.font(13, "bold"), text_color=theme.MUTED
            )
            self.level_values[key].pack(side="right")
            today.add(lvl, pady=(2, 6), always_enabled=True)
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
        act = Card(self.tabs.tab("Journal"), ctx, "Activity journal", expand=True)
        act.grid(row=0, column=0, sticky="nsew", padx=4, pady=8)
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
            bar, text="↓ Follow", command=self.follow, height=26, width=80, fg_color=theme.GRAPHITE
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
            font=ctk.CTkFont(family=theme.MONO_FAMILY, size=12),
            wrap="word",
            height=220,
            state="disabled",
        )
        stabilize_textbox(self.textbox)
        act.add(self.textbox, always_enabled=True, expand=True, pady=(0, 0))
        self._lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._placeholder = True
        self._set_text("Nothing yet. Choose START or SIMULATE in the session console.")
        self._detached = False
        ctx.window.session.update_log(self._lines)

        self.refresh_today()
        ctx.register_tick(self.refresh_today)
        ctx.register_tick(self.refresh_routines)

    def _build_routines(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="YOUR ROUTINES",
            anchor="w",
            font=theme.font(25, "bold", theme.DISPLAY_FAMILY),
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(12, 0))
        intro = ctk.CTkLabel(
            parent,
            text="Everything in its place. Configure a routine to get started.",
            anchor="w",
            justify="left",
            text_color=theme.MUTED,
            font=theme.font(13),
            wraplength=420,
        )
        intro.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 16))
        autowrap(parent, [intro], offset=24)
        self.routine_values = {}
        self.routine_buttons = {}
        for index, routine in enumerate(ROUTINES):
            tile = ctk.CTkFrame(parent, border_width=2, border_color=theme.BORDER, corner_radius=5)
            tile.grid(row=index + 2, column=0, sticky="ew", padx=4, pady=(0, 12))
            tile.grid_columnconfigure(1, weight=1)
            number = ctk.CTkLabel(
                tile,
                text=f"{index + 1:02}",
                width=64,
                height=90,
                fg_color=theme.GRAPHITE,
                text_color=theme.BRASS,
                corner_radius=3,
                font=theme.font(33, "bold", theme.DISPLAY_FAMILY),
            )
            number.grid(row=0, column=0, rowspan=3, padx=12, pady=12, sticky="ns")
            title = ctk.CTkLabel(
                tile,
                text=routine.title.upper(),
                anchor="w",
                font=theme.font(19, "bold", theme.DISPLAY_FAMILY),
            )
            title.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(12, 0))
            description = ctk.CTkLabel(
                tile,
                text=routine.description,
                anchor="w",
                justify="left",
                wraplength=300,
                text_color=theme.MUTED,
                font=theme.font(12),
            )
            description.grid(row=1, column=1, sticky="w", padx=(0, 12))
            status = ctk.CTkLabel(tile, text="", anchor="w", font=theme.font(12))
            status.grid(row=2, column=1, sticky="w", pady=(0, 10))
            button = ctk.CTkButton(
                tile,
                text="CONFIGURE  >",
                width=126,
                height=34,
                font=theme.font(12, "bold"),
                command=lambda page=routine.page: self.ctx.show_page(page),
            )
            button.grid(row=3, column=1, sticky="w", pady=(0, 12))
            self.routine_values[routine.page] = status
            self.routine_buttons[routine.page] = button

            def fit_tile(event, button=button, labels=(title, description, status)):
                wide = event.width >= 610
                target = (0, 2, 3) if wide else (3, 1, 1)
                if int(button.grid_info()["column"]) != target[1]:
                    button.grid_configure(
                        row=target[0],
                        column=target[1],
                        rowspan=target[2],
                        padx=(0, 12),
                        pady=12,
                        sticky="e" if wide else "w",
                    )
                wrap = max(180, event.width - (252 if wide else 120))
                for label in labels:
                    if label.cget("wraplength") != wrap:
                        label.configure(wraplength=wrap)

            tile.bind("<Configure>", fit_tile, add="+")
        note = ctk.CTkLabel(
            parent,
            text="Switch counts reflect your configuration, not live progress.\n"
            "Changes save automatically; the session console shows actual activity.",
            justify="left",
            anchor="w",
            text_color=theme.MUTED,
            wraplength=460,
            font=theme.font(12),
        )
        note.grid(row=6, column=0, sticky="w", padx=8, pady=(0, 12))
        autowrap(parent, [note], offset=24)
        self.refresh_routines()

    def refresh_routines(self) -> None:
        for routine in ROUTINES:
            count = enabled_count(self.ctx.settings, routine)
            text = f"{count} / {len(routine.switches)} switches enabled"
            label = self.routine_values[routine.page]
            if label.cget("text") != text:
                label.configure(text=text, text_color=theme.OK if count else theme.MUTED)

    # -- state ------------------------------------------------------------------------------
    def set_state(self, text: str, kind: str, cycle: int | None, duration: str = "") -> None:
        self.pill.set(text, kind)
        c = f"LAST CYCLE  {cycle}" if cycle else "CYCLE  —"
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
        full = len(self._lines) == MAX_LOG_LINES
        self._lines.append(entry)
        self.textbox.configure(state="normal")
        if full:
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
        self.ctx.window.session.update_log(self._lines)

    def follow(self) -> None:
        self._detached = False
        self.textbox.see("end")
        self.follow_btn.pack_forget()

    def clear_log(self) -> None:
        self._lines.clear()
        self._placeholder = True
        self._set_text("Nothing yet. Choose START or SIMULATE in the session console.")
        self.count_label.configure(text="0 lines")
        self.ctx.window.session.update_log(self._lines)
        self.follow()

    def copy_log(self) -> None:
        self.textbox.clipboard_clear()
        self.textbox.clipboard_append("\n".join(self._lines))


def build(parent, ctx: PageContext):
    view = DashboardView(parent, ctx)
    ctx.extras["dashboard"] = view
    return view.frame


def _load_progress(path: str):
    """The account / guild levels read by the bot (progress.py), empty when not written yet."""
    from firestone_bot.progress import Progress

    return Progress.load(path)
