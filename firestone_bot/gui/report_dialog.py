"""Send report dialog (owner request, 2026-10-22): the player says what went wrong, the report
zip is built and uploaded off the Tk thread (firestone_bot.report), and the player gets an ID
to give on Discord. When the upload fails, the zip can be saved and sent another way.

Not modal: a grab would leave the mouse guard's pause pop-up without working buttons while
the bot runs. The main window keeps one dialog at a time."""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Callable

from firestone_bot import report
from firestone_bot.gui import theme

log = logging.getLogger("firestone_bot.gui")

WHAT = (
    "The report holds the bot's newest logs (your user folder shows as ~), your settings "
    "without your Discord ID and client ID, and the latest screenshots the bot saved in its "
    "diagnostics folder. It goes to the maintainer's server only, with the bot's client ID. "
    "You get a report ID: give it on Discord."
)


class ReportDialog:
    """A note, two choices, Send / Save as file / Close, and the outcome."""

    def __init__(
        self,
        parent,
        base_dir: str,
        settings,
        env_now: dict | None = None,
        persist: Callable[[], None] | None = None,
    ) -> None:
        import customtkinter as ctk

        from firestone_bot.features import heartbeat
        from firestone_bot.gui.widgets import apply_window_icon

        self.base_dir = base_dir
        self.settings = settings  # read on the Tk thread only
        fresh = not settings.get("ClientID").strip()
        # no save from here: the binder saves it, deferred while the bot runs
        self.client_id = heartbeat.get_unique_id(settings, save=False)
        if fresh and persist is not None:
            persist()
        self.discord_id = settings.get("DiscordID").strip()
        self.env_now = dict(env_now or {})
        self.results: queue.Queue = queue.Queue()
        self.built: tuple[tuple, bytes] | None = None  # (what it was built from, zip)
        self.busy = False
        self.report_id = ""

        width, height = 620, 520
        self.top = ctk.CTkToplevel(parent)
        self.top.title("Send report")
        apply_window_icon(self.top)
        self.top.transient(parent)
        self.top.resizable(True, True)
        self.top.minsize(width, 480)
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.top.geometry(
            f"{width}x{height}+{max(0, px + (pw - width) // 2)}+{max(0, py + (ph - height) // 2)}"
        )
        self.top.grid_columnconfigure(0, weight=1)
        self.top.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self.top, fg_color=theme.BANNER_BG["info"], corner_radius=0)
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            head, text="Send a report", font=theme.font(20, "bold"), text_color=theme.INFO
        ).pack(anchor="w", padx=24, pady=(18, 2))
        ctk.CTkLabel(
            head,
            text=WHAT,
            font=theme.font(12),
            text_color=theme.MUTED,
            justify="left",
            anchor="w",
            wraplength=width - 48,
        ).pack(anchor="w", padx=24, pady=(0, 16))

        ctk.CTkLabel(
            self.top,
            text=f"What went wrong? (optional, {report.NOTE_MAX} characters at most)",
            font=theme.font(13, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 4))
        self.note = ctk.CTkTextbox(self.top, wrap="word", font=theme.font(13), height=110)
        self.note.grid(row=2, column=0, sticky="nsew", padx=24)

        choices = ctk.CTkFrame(self.top, fg_color="transparent")
        choices.grid(row=3, column=0, sticky="ew", padx=24, pady=(10, 0))
        self.with_captures = ctk.BooleanVar(master=self.top, value=True)
        ctk.CTkCheckBox(
            choices,
            text="Include the screenshots (anything that was over the game then is in them)",
            variable=self.with_captures,
            font=theme.font(12),
        ).pack(anchor="w")
        # the heartbeat is the player's existing opt-in to share the Discord ID
        self.with_discord = ctk.BooleanVar(
            master=self.top, value=bool(settings.flag("EnableHeartbeat"))
        )
        if self.discord_id:
            ctk.CTkCheckBox(
                choices,
                text=f"Send my Discord ID ({self.discord_id}) so the maintainer can reach me",
                variable=self.with_discord,
                font=theme.font(12),
            ).pack(anchor="w", pady=(6, 0))

        self.status = ctk.CTkLabel(
            self.top,
            text="",
            font=theme.font(13),
            justify="left",
            anchor="w",
            wraplength=width - 48,
        )
        self.status.grid(row=4, column=0, sticky="ew", padx=24, pady=(10, 0))

        row = ctk.CTkFrame(self.top, fg_color="transparent")
        row.grid(row=5, column=0, sticky="ew", padx=24, pady=(10, 18))
        secondary = {"fg_color": "transparent", "border_width": 1, "text_color": theme.MUTED}
        self.send_btn = ctk.CTkButton(
            row, text="Send", width=120, height=34, font=theme.font(13, "bold"), command=self._send
        )
        self.send_btn.pack(side="right", padx=(8, 0))
        self.save_btn = ctk.CTkButton(
            row, text="Save as file…", width=130, height=34, command=self._save, **secondary
        )
        self.save_btn.pack(side="right", padx=(8, 0))
        self.copy_btn = ctk.CTkButton(
            row, text="Copy ID", width=100, height=34, command=self._copy, **secondary
        )
        self.close_btn = ctk.CTkButton(
            row, text="Close", width=100, height=34, command=self._close, **secondary
        )
        self.close_btn.pack(side="left")

        self.top.protocol("WM_DELETE_WINDOW", self._close)
        self.top.bind("<Escape>", lambda _e: self._close())
        self.top.after(50, self._raise)
        self.top.after(100, self._poll)

    def alive(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except Exception:  # noqa: BLE001 - the window is gone
            return False

    # -- actions ------------------------------------------------------------------------------
    def _note_text(self) -> str:
        return self.note.get("1.0", "end").strip()[: report.NOTE_MAX]

    def _send(self) -> None:
        self._start(None)

    def _save(self) -> None:
        from tkinter import filedialog

        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = filedialog.asksaveasfilename(
            parent=self.top,
            title="Save the report",
            defaultextension=".zip",
            initialfile=f"firestone-bot-report-{stamp}.zip",
            filetypes=[("Zip archive", "*.zip")],
        )
        if path:
            self._start(path)

    def _start(self, save_to: str | None) -> None:
        if self.busy:
            return
        self.busy = True
        for button in (self.send_btn, self.save_btn):
            button.configure(state="disabled")
        self._say("Building the report…", theme.MUTED)
        # everything the worker needs, read here on the Tk thread: the settings in memory
        # (never settings.ini, which the bot thread may be replacing)
        job = {
            "note": self._note_text(),
            "captures": bool(self.with_captures.get()),
            "settings": self.settings.text(),
            "discord_id": self.discord_id if self.with_discord.get() else "",
            "save_to": save_to,
        }
        threading.Thread(target=self._work, args=(job,), name="send-report", daemon=True).start()

    def _work(self, job: dict) -> None:
        """Off the Tk thread: build (once per choice), then upload or save; answers via a
        queue. Outcomes are logged here: the dialog may be closed while it sends."""
        try:
            key = (job["note"], job["captures"])
            if self.built is None or self.built[0] != key:
                data = report.build(
                    self.base_dir,
                    job["settings"],
                    job["note"],
                    self.env_now,
                    captures=job["captures"],
                )
                self.built = (key, data)
            data = self.built[1]
            if job["save_to"]:
                with open(job["save_to"], "wb") as f:
                    f.write(data)
                log.info("Report saved: %s", os.path.basename(job["save_to"]))
                self.results.put(("saved", job["save_to"]))
                return
            self.results.put(("sending", len(data)))
            answer = report.upload(data, self.client_id, job["discord_id"], job["note"])
            log.info("Report sent: %s (%s bytes)", answer.get("id"), answer.get("size"))
            self.results.put(("sent", answer))
        except (report.ReportError, OSError) as e:
            log.info("Report not sent: %s", e)
            self.results.put(("failed", str(e)))
        except Exception as e:  # said in the dialog, the bot goes on
            log.exception("report failed")
            self.results.put(("failed", f"unexpected error: {e}"))

    def _poll(self) -> None:
        if not self.alive():
            return
        while True:
            try:
                kind, value = self.results.get_nowait()
            except queue.Empty:
                break
            self._show(kind, value)
        self.top.after(100, self._poll)

    def _show(self, kind: str, value) -> None:
        if kind == "sending":
            self._say(f"Sending the report ({value / 1024 / 1024:.1f} MB)…", theme.MUTED)
            return
        self.busy = False
        self.save_btn.configure(state="normal")
        if kind == "sent":
            self.report_id = str(value.get("id"))
            self._say(f"Report sent: {self.report_id}. Give this ID on Discord.", theme.OK)
            self.copy_btn.pack(side="right", padx=(8, 0))
        elif kind == "saved":
            self._say(f"Report saved: {os.path.basename(value)}", theme.OK)
        else:
            self._say(
                f"Not sent: {value}. You can save it as a file and send it another way.",
                theme.ERR,
            )
        # sent once: a second Send would file the same report again
        self.send_btn.configure(state="disabled" if self.report_id else "normal")

    def _say(self, text: str, colour) -> None:
        self.status.configure(text=text, text_color=colour)

    def _copy(self) -> None:
        if self.report_id:
            self.top.clipboard_clear()
            self.top.clipboard_append(self.report_id)
            self._say(f"Report sent: {self.report_id}. Copied: paste it on Discord.", theme.OK)

    # -- window -------------------------------------------------------------------------------
    def _raise(self) -> None:
        try:
            self.top.lift()
            self.note.focus_set()
        except Exception:
            log.debug("report dialog raise failed (window gone?)", exc_info=True)

    def _close(self) -> None:
        """Closing while it builds or sends only hides the dialog: the upload goes on, the
        worker logs its outcome, and Send report shows it again with the report ID."""
        try:
            if self.busy:
                self.top.withdraw()
                return
            self.top.destroy()
        except Exception:
            log.debug("dialog close failed", exc_info=True)
