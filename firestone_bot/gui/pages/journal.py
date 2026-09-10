"""The actual session log, retained by MainWindow independently of the active skin."""

from __future__ import annotations

from collections import deque

import customtkinter as ctk

from firestone_bot.gui import theme
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import autowrap, stabilize_textbox


class JournalView:
    def __init__(self, parent, ctx: PageContext) -> None:
        self.ctx = ctx
        self.window = ctx.window
        self.frame = ctk.CTkFrame(parent, fg_color=theme.PAPER, corner_radius=0)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(
            self.frame,
            text="The session journal.",
            anchor="w",
            font=theme.heading(32),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 4))
        subtitle = ctk.CTkLabel(
            self.frame,
            text="Activity messages from the bot, as they happen.",
            anchor="w",
            justify="left",
            text_color=theme.MUTED,
            font=theme.font(13),
        )
        subtitle.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 18))
        autowrap(self.frame, [subtitle], offset=56)
        toolbar = ctk.CTkFrame(self.frame, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 12))
        toolbar.grid_columnconfigure(4, weight=1)
        self.actions = {}
        for index, (key, label, command) in enumerate(
            (
                ("copy", "Copy all", self.copy_log),
                ("open_log", "Open log file", lambda: ctx.call("open_log")),
                ("clear", "Clear view", self.clear_log),
            )
        ):
            button = ctk.CTkButton(
                toolbar,
                text=label,
                command=command,
                height=34,
                width=110,
                fg_color=theme.SURFACE,
                text_color=theme.TEXT,
                border_width=1,
                border_color=theme.BORDER,
                hover_color=theme.SURFACE_ALT,
            )
            button.grid(row=0, column=index, padx=(0, 8))
            self.actions[key] = button
        self.follow_btn = ctk.CTkButton(
            toolbar,
            text="Follow latest",
            command=self.follow,
            height=34,
            width=116,
        )
        self.follow_btn.grid(row=0, column=3)
        self.actions["follow"] = self.follow_btn
        self.count_label = ctk.CTkLabel(
            toolbar,
            text="",
            anchor="e",
            text_color=theme.MUTED,
            font=theme.font(12),
        )
        self.count_label.grid(row=0, column=4, sticky="e", padx=(12, 0))
        self.textbox = ctk.CTkTextbox(
            self.frame,
            font=theme.mono(12),
            wrap="word",
            state="disabled",
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=8,
        )
        self.textbox.grid(row=3, column=0, sticky="nsew", padx=28, pady=(0, 24))
        stabilize_textbox(self.textbox)
        self._line_sizes: deque[int] = deque()
        self._render()

    def _render(self) -> None:
        entries = self.window.log_lines
        self._line_sizes = deque(entry.count("\n") + 1 for entry in entries)
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert(
            "end",
            "\n".join(entries) + "\n"
            if entries
            else "No activity yet. Start the bot or run a dry run to see its messages here.",
        )
        self.textbox.configure(state="disabled")
        if self.window.log_follow:
            self.textbox.see("end")
        else:
            self.textbox.yview_moveto(self.window.log_scroll)
        self._update_count()

    def _update_count(self) -> None:
        count = len(self.window.log_lines)
        self.count_label.configure(text=f"{count} message{'s' if count != 1 else ''}")
        self.follow_btn.configure(
            text="Following latest" if self.window.log_follow else "Follow latest"
        )

    def capture_state(self) -> None:
        self.window.log_scroll = self.textbox.yview()[0]
        if self.textbox.yview()[1] < 0.999:
            self.window.log_follow = False

    def append_entry(self, entry: str, was_full: bool) -> None:
        at_end = self.textbox.yview()[1] >= 0.999
        if self._line_sizes and not at_end:
            self.window.log_follow = False
        self.textbox.configure(state="normal")
        if not self._line_sizes:
            self.textbox.delete("1.0", "end")
        elif was_full:
            removed = self._line_sizes.popleft()
            self.textbox.delete("1.0", f"{removed + 1}.0")
        self.textbox.insert("end", entry + "\n")
        self._line_sizes.append(entry.count("\n") + 1)
        self.textbox.configure(state="disabled")
        if self.window.log_follow:
            self.textbox.see("end")
        self._update_count()

    def follow(self) -> None:
        self.window.log_follow = True
        self.textbox.see("end")
        self._update_count()

    def clear_log(self) -> None:
        """Clear the in-memory view; the log file remains available for diagnostics."""
        self.window.log_lines.clear()
        self.window.log_follow = True
        self.window.log_scroll = 0.0
        self._render()

    def copy_log(self) -> None:
        self.textbox.clipboard_clear()
        self.textbox.clipboard_append("\n".join(self.window.log_lines))


def build(parent, ctx: PageContext):
    view = JournalView(parent, ctx)
    ctx.extras["journal"] = view
    return view.frame
