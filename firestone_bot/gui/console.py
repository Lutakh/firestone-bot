"""Native retro console chrome: a pixel emblem and a persistent session panel."""

from __future__ import annotations

import time
import tkinter as tk

import customtkinter as ctk

from firestone_bot.gui import theme
from firestone_bot.gui.widgets import Card, StatePill, autowrap, stabilize_textbox


class Flame(tk.Canvas):
    """Small code-drawn pixel emblem; no external fonts or image files required."""

    def __init__(self, parent):
        super().__init__(parent, width=42, height=48, bg=theme.GRAPHITE, highlightthickness=0, bd=0)
        pixels = [
            "      x   ",
            "     xx   ",
            "    xox   ",
            "   xoox x ",
            "   xooxox ",
            "  xoooyox ",
            " xoooyyox ",
            " xooyyyox ",
            " xooyyyox ",
            "  xoyyox  ",
            "   xxxx   ",
        ]
        colors = {"x": theme.CREAM, "o": "#ca682b", "y": theme.BRASS}
        for y, row in enumerate(pixels):
            for x, color in enumerate(row):
                if color in colors:
                    self.create_rectangle(
                        x * 4, y * 4, x * 4 + 4, y * 4 + 4, fill=colors[color], outline=""
                    )


class SessionPanel(ctk.CTkFrame):
    """Commands stay in one place while users configure any routine."""

    def __init__(self, parent, ctx):
        super().__init__(
            parent, width=300, corner_radius=5, border_width=2, border_color=theme.BORDER
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_propagate(False)
        self.started_at = None
        self.elapsed = 0
        self.running = False
        session = Card(self, ctx, "Session")
        session.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        self.pill = StatePill(session.body)
        session.add(self.pill)
        self.cycle_label = ctk.CTkLabel(
            session.body,
            text="CYCLE  —",
            anchor="w",
            font=theme.font(20, "bold", theme.DISPLAY_FAMILY),
        )
        session.add(self.cycle_label, pady=(8, 2))
        session.note("CURRENT ACTIVITY")
        self.activity_label = ctk.CTkLabel(
            session.body,
            text="Ready to start",
            anchor="w",
            justify="left",
            wraplength=244,
            height=48,
            font=theme.font(14, "bold"),
        )
        session.add(self.activity_label)
        self.timer = ctk.CTkLabel(
            session.body,
            text="00:00:00",
            height=50,
            fg_color=theme.GRAPHITE,
            text_color=theme.BRASS,
            corner_radius=3,
            font=theme.font(29, "bold", theme.MONO_FAMILY),
        )
        session.add(self.timer, pady=(8, 0))
        session.note("SESSION TIME", wrap=240)
        self.stop_btn = ctk.CTkButton(
            session.body,
            text="■  STOP BOT",
            height=42,
            fg_color=theme.STOP,
            hover_color=theme.STOP_HOVER,
            command=lambda: ctx.call("stop"),
            font=theme.font(15, "bold", theme.DISPLAY_FAMILY),
        )
        session.add(self.stop_btn, pady=(8, 6))
        row = ctk.CTkFrame(session.body, fg_color="transparent")
        row.grid_columnconfigure((0, 1), weight=1, uniform="commands")
        self.start_btn = ctk.CTkButton(
            row, text="START", width=80, height=34, command=lambda: ctx.call("start")
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.dry_btn = ctk.CTkButton(
            row, text="SIMULATE", width=80, height=34, command=lambda: ctx.call("dry_run")
        )
        self.dry_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        session.add(row)
        self.window_banner = session.banner(
            "warn",
            "Game window not found. Open Firestone, then re-check in Diagnostics.",
            visible=False,
        )
        self.open_log_btn = ctk.CTkButton(
            session.body, text="Open error log", command=lambda: ctx.call("open_log"), height=28
        )
        session.add(self.open_log_btn)
        self.open_log_btn.grid_remove()
        autowrap(session.body, [self.activity_label, self.window_banner.label], offset=4)
        log = Card(self, ctx, "Journal", expand=True)
        log.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.recent = ctk.CTkTextbox(
            log.body,
            height=90,
            wrap="word",
            state="disabled",
            font=theme.font(12, family=theme.MONO_FAMILY),
        )
        stabilize_textbox(self.recent)
        log.add(self.recent, expand=True)
        log.buttons(("View full journal", lambda: ctx.window.show_dashboard_tab("Journal")))
        ctx.register_tick(self.tick)

    def set_running(self, running: bool) -> None:
        if running and not self.running:
            self.started_at = time.monotonic()
            self.elapsed = 0
        elif self.running and not running and self.started_at is not None:
            self.elapsed = int(time.monotonic() - self.started_at)
            self.started_at = None
        self.running = running
        self.tick()

    def tick(self) -> None:
        elapsed = (
            int(time.monotonic() - self.started_at) if self.started_at is not None else self.elapsed
        )
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        value = f"{hours:02}:{minutes:02}:{seconds:02}"
        if self.timer.cget("text") != value:
            self.timer.configure(text=value)

    def update_log(self, lines) -> None:
        self.recent.configure(state="normal")
        self.recent.delete("1.0", "end")
        # The complete entry is available in Journal; keep this rail compact.
        self.recent.insert(
            "end", "\n\n".join(line[:180] for line in list(lines)[-3:]) or "No activity yet."
        )
        self.recent.configure(state="disabled")
        self.recent.see("end")
