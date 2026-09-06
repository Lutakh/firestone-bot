"""Update dialog: a styled modal showing the release notes (owner request 2026-09-06, replacing
the tkinter message boxes).

`render_notes` turns the GitHub release body (Markdown) into styled runs for a CTkTextbox:
"## Title" headings, "- item" bullets, **bold** spans, blank lines; everything else is plain
text. It is a pure function (unit-tested); the dialog itself needs a display.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from firestone_bot.gui import theme

log = logging.getLogger("firestone_bot.gui")

Run = tuple[str, str]  # (text, tag) with tag in "h1", "h2", "bullet", "bold", "text"

_BOLD = re.compile(r"\*\*(.+?)\*\*")


def render_notes(notes: str) -> list[Run]:
    """Markdown-ish release notes -> list of (text, tag) runs, newline-terminated lines."""
    runs: list[Run] = []
    for raw in (notes or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            runs.append(("\n", "text"))
            continue
        if line.startswith("# "):
            runs.append((line[2:].strip() + "\n", "h1"))
            continue
        if line.startswith(("## ", "### ")):
            runs.append((line.split(" ", 1)[1].strip() + "\n", "h2"))
            continue
        body = line
        prefix = ""
        if re.match(r"\s*[-*] ", line):
            prefix = "•  "
            body = re.sub(r"^\s*[-*] ", "", line)
        if prefix:
            runs.append((prefix, "bullet"))
        pos = 0
        for m in _BOLD.finditer(body):
            if m.start() > pos:
                runs.append((body[pos : m.start()], "text"))
            runs.append((m.group(1), "bold"))
            pos = m.end()
        if pos < len(body):
            runs.append((body[pos:], "text"))
        runs.append(("\n", "text"))
    while runs and runs[-1] == ("\n", "text"):
        runs.pop()
    return runs


class UpdateDialog:
    """Modal window: title, version line, rendered notes, action buttons.

    `buttons` is a list of (label, callback, primary); the dialog closes itself before calling
    the callback. Escape / the window X call `on_close` (or nothing)."""

    def __init__(
        self,
        parent,
        title: str,
        headline: str,
        notes: str,
        buttons: list[tuple[str, Callable[[], None] | None, bool]],
        subtitle: str = "",
        width: int = 640,
        height: int = 520,
    ) -> None:
        import customtkinter as ctk

        from firestone_bot.gui.widgets import apply_window_icon

        self.top = ctk.CTkToplevel(parent)
        self.top.title(title)
        apply_window_icon(self.top)
        self.top.transient(parent)
        self.top.resizable(True, True)
        self.top.minsize(480, 360)
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = max(0, px + (pw - width) // 2)
        y = max(0, py + (ph - height) // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        self.top.grid_columnconfigure(0, weight=1)
        self.top.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self.top, fg_color=theme.BANNER_BG["info"], corner_radius=0)
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            head, text=headline, font=theme.font(20, "bold"), text_color=theme.INFO, anchor="w"
        ).pack(anchor="w", padx=24, pady=(18, 2 if subtitle else 18))
        if subtitle:
            ctk.CTkLabel(
                head, text=subtitle, font=theme.font(12), text_color=theme.MUTED, anchor="w"
            ).pack(anchor="w", padx=24, pady=(0, 16))

        self.box = ctk.CTkTextbox(
            self.top, wrap="word", font=theme.font(13), activate_scrollbars=True
        )
        self.box.grid(row=1, column=0, sticky="nsew", padx=24, pady=(16, 8))
        t = self.box._textbox  # the underlying tk.Text carries the tags
        t.tag_configure("h1", font=theme.font(17, "bold"), spacing1=10, spacing3=4)
        t.tag_configure("h2", font=theme.font(14, "bold"), spacing1=12, spacing3=4)
        t.tag_configure("bold", font=theme.font(13, "bold"))
        t.tag_configure("bullet", lmargin1=8, lmargin2=26)
        t.tag_configure("text", lmargin1=8, lmargin2=26, spacing3=2)
        runs = render_notes(notes) or [("No release notes.", "text")]
        for text, tag in runs:
            t.insert("end", text, tag)
        self.box.configure(state="disabled")

        row = ctk.CTkFrame(self.top, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=24, pady=(4, 18))
        for label, cb, primary in reversed(buttons):
            kw = (
                {}
                if primary
                else {"fg_color": "transparent", "border_width": 1, "text_color": theme.MUTED}
            )
            ctk.CTkButton(
                row,
                text=label,
                height=34,
                width=150,
                font=theme.font(13, "bold" if primary else "normal"),
                command=lambda cb=cb: self._fire(cb),
                **kw,
            ).pack(side="right", padx=(8, 0))
        self.on_close: Callable[[], None] | None = None
        self.top.protocol("WM_DELETE_WINDOW", lambda: self._fire(self.on_close))
        self.top.bind("<Escape>", lambda _e: self._fire(self.on_close))
        self.top.after(50, self._modal)

    def _modal(self) -> None:
        try:
            self.top.grab_set()
            self.top.focus_force()
            self.top.lift()
        except Exception:
            log.debug("modal grab failed (window gone?)", exc_info=True)

    def _fire(self, cb: Callable[[], None] | None) -> None:
        try:
            self.top.grab_release()
            self.top.destroy()
        except Exception:
            log.debug("dialog close failed", exc_info=True)
        if cb is not None:
            cb()
