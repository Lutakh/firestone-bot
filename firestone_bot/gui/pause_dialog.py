"""Pop-up shown when the input guard paused the bot (inputguard.py): start a new cycle or
continue, with a countdown that restarts on every new movement of the user."""

from __future__ import annotations

from collections.abc import Callable

from firestone_bot.gui import theme


class PauseDialog:
    def __init__(self, parent, guard, decide: Callable[[str], None]) -> None:
        import customtkinter as ctk

        from firestone_bot.gui.widgets import apply_window_icon

        self.guard = guard
        self.decide = decide
        self.done = False
        self.top = ctk.CTkToplevel(parent)
        self.top.title("Firestone bot paused")
        apply_window_icon(self.top)
        self.top.attributes("-topmost", True)
        self.top.resizable(False, False)
        width, height = 520, 300
        sw, sh = parent.winfo_screenwidth(), parent.winfo_screenheight()
        self.top.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 3}")
        self.top.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(self.top, fg_color=theme.BANNER_BG["warn"], corner_radius=0)
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            head,
            text="You used the mouse or the keyboard",
            font=theme.font(18, "bold"),
            text_color=theme.colour("warn"),
            anchor="w",
        ).pack(anchor="w", padx=24, pady=16)
        ctk.CTkLabel(
            self.top,
            text=(
                f"The bot paused ({guard.reason}). Start a new cycle from the beginning "
                "(the bot goes back to the main screen by itself), or continue the cycle "
                "where it stopped?"
            ),
            font=theme.font(13),
            wraplength=470,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 8))
        self.countdown = ctk.CTkLabel(
            self.top,
            text="",
            font=theme.font(13, "bold"),
            text_color=theme.MUTED,
            wraplength=470,
            justify="left",
            anchor="w",
        )
        self.countdown.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        row = ctk.CTkFrame(self.top, fg_color="transparent")
        row.grid(row=3, column=0, sticky="ew", padx=24, pady=(4, 18))
        ctk.CTkButton(
            row,
            text="Start a new cycle",
            height=34,
            width=170,
            font=theme.font(13, "bold"),
            command=lambda: self._fire("restart"),
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            row,
            text="Continue the cycle",
            height=34,
            width=170,
            font=theme.font(13),
            fg_color="transparent",
            border_width=1,
            text_color=theme.MUTED,
            command=lambda: self._fire("continue"),
        ).pack(side="right", padx=(8, 0))
        self.top.protocol("WM_DELETE_WINDOW", lambda: self._fire("restart"))
        self.top.after(50, self._lift)
        self._tick()

    def _lift(self) -> None:
        import tkinter as tk

        try:
            self.top.lift()
            self.top.focus_force()
        except tk.TclError:  # the window is gone already
            return

    def _tick(self) -> None:
        if self.done:
            return
        left = self.guard.remaining()
        if left <= 0:
            self._fire("restart")
            return
        self.countdown.configure(
            text=f"Without an answer, a new cycle starts in {int(left) + 1} s "
            "(the countdown restarts when the mouse moves)."
        )
        self.top.after(250, self._tick)

    def _fire(self, decision: str) -> None:
        if self.done:
            return
        self.done = True
        try:
            self.top.destroy()
        finally:
            self.decide(decision)
