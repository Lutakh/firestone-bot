"""Launcher-wide discovery that opens destinations without executing their actions."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from firestone_bot.gui import theme
from firestone_bot.gui.search_catalog import SearchResult, search_launcher
from firestone_bot.gui.widgets import (
    Entry,
    ScrollableFrame,
    bind_platform_wheel,
    register_cleanup,
    trace_variable,
)

SEARCH_DELAY_MS = 140
RESULT_BATCH_SIZE = 20


def _location(result: SearchResult) -> str:
    page = result.page.replace("_", " ").title()
    section = result.section.replace("_", " ").title()
    return f"{page} / {section}" if section else page


class LauncherSearch(ctk.CTkFrame):
    """Compact search field with a disposable overlay and keyboard navigation."""

    def __init__(self, parent, *, on_select: Callable[[SearchResult], None]):
        super().__init__(parent, fg_color="transparent", height=34, corner_radius=0)
        self.on_select = on_select
        self.query_var = tk.StringVar(master=self)
        self.results: list[SearchResult] = []
        self._result_buttons: list[ctk.CTkButton] = []
        self._selected_index = -1
        self._search_after: str | None = None
        self._position_after: str | None = None
        self._reveal_after: str | None = None
        self._visible = False
        self._alive = True
        self._top = self.winfo_toplevel()
        self._more_button = None
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Search launcher",
            font=theme.font(12, "bold"),
            text_color=theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, padx=(0, 10))
        self.entry = Entry(self, textvariable=self.query_var, height=32, font=theme.font(12))
        self.entry.grid(row=0, column=1, sticky="ew")
        self.clear_button = ctk.CTkButton(
            self,
            text="Clear",
            width=54,
            height=30,
            fg_color="transparent",
            hover_color=theme.SURFACE_ALT,
            text_color=theme.MUTED,
            font=theme.font(11),
            command=self._clear,
            state="disabled",
        )
        self.clear_button.grid(row=0, column=2, padx=(4, 0))
        ctk.CTkLabel(
            self,
            text="Ctrl+K",
            font=theme.mono(10),
            text_color=theme.MUTED,
        ).grid(row=0, column=3, padx=(8, 0))

        # Owning this panel at the toplevel lets it cover sibling pages without
        # reserving vertical space or being clipped to the search field's height.
        self.popup = ctk.CTkFrame(
            self._top,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=theme.RADIUS,
        )
        self.popup.grid_columnconfigure(0, weight=1)
        self.popup.grid_rowconfigure(1, weight=1)
        self.count_label = ctk.CTkLabel(
            self.popup,
            text="",
            anchor="w",
            font=theme.font(12, "bold"),
            text_color=theme.TEXT,
        )
        self.count_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(5, 0))
        self.library = ScrollableFrame(self.popup, fg_color="transparent", corner_radius=0)
        self.library.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 3))
        self.library.grid_columnconfigure(0, weight=1)
        bind_platform_wheel(self.library)
        self.empty_label = ctk.CTkLabel(
            self.library,
            text="No matches. Try a setting, feature or action, such as update or restart.",
            anchor="w",
            justify="left",
            font=theme.font(12),
            text_color=theme.MUTED,
        )
        ctk.CTkLabel(
            self.popup,
            text="Up / Down to choose  ·  Enter to open  ·  Esc to close",
            anchor="w",
            font=theme.font(10),
            text_color=theme.MUTED,
            height=20,
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 5))

        trace_variable(self, self.query_var, self._query_changed)
        self.entry.bind("<Down>", lambda _event: self._move(1))
        self.entry.bind("<Up>", lambda _event: self._move(-1))
        self.entry.bind("<Return>", lambda _event: self._activate())
        self.entry.bind("<Escape>", lambda _event: self._escape())
        self.entry.bind("<Button-1>", lambda _event: self._reopen())
        self._top_bindings = [
            ("<Configure>", self._top.bind("<Configure>", self._configured, add="+")),
            ("<Button-1>", self._top.bind("<Button-1>", self._outside_click, add="+")),
        ]
        register_cleanup(self, self._dispose)

    def focus_search(self) -> None:
        """Focus the shared field and select its query for quick replacement."""
        self.entry.focus_set()
        self.entry.select_range(0, "end")
        self._reopen()

    def close_results(self) -> None:
        """Dismiss the overlay, retaining the query for the next search."""
        self._cancel("_search_after")
        self._cancel("_position_after")
        self._cancel("_reveal_after")
        self._visible = False
        self.popup.place_forget()

    def refresh_results(self) -> None:
        """Apply the current query immediately; used after debounce or Enter."""
        self._cancel("_search_after")
        query = self.query_var.get().strip()
        if not query:
            self.close_results()
            self.results = []
            self._selected_index = -1
            return
        self._cancel("_reveal_after")
        self.results = search_launcher(query, limit=None)
        self._selected_index = 0 if self.results else -1
        for button in self._result_buttons:
            button.destroy()
        self._result_buttons.clear()
        if self._more_button is not None:
            self._more_button.destroy()
            self._more_button = None
        self.empty_label.grid_forget()
        count = len(self.results)
        self.count_label.configure(text=f"{count} {'result' if count == 1 else 'results'}")
        if count:
            self._append_results()
        else:
            self.empty_label.grid(row=0, column=0, sticky="ew", padx=7, pady=16)
        self.library._parent_canvas.yview_moveto(0)
        self._visible = True
        self._position_popup()

    def _query_changed(self, *_args) -> None:
        self._cancel("_search_after")
        self.clear_button.configure(state="normal" if self.query_var.get() else "disabled")
        if not self.query_var.get().strip():
            self.refresh_results()
        else:
            self._search_after = self.after(SEARCH_DELAY_MS, self.refresh_results)

    def _clear(self) -> None:
        self.query_var.set("")
        self.entry.focus_set()

    def _reopen(self) -> None:
        if self._alive and self.query_var.get().strip() and not self._visible:
            self.refresh_results()

    def _append_results(self) -> None:
        if self._more_button is not None:
            self._more_button.destroy()
            self._more_button = None
        start = len(self._result_buttons)
        end = min(len(self.results), start + RESULT_BATCH_SIZE)
        for index in range(start, end):
            result = self.results[index]
            location = _location(result)
            description = " ".join(result.description.split())
            if len(description) > 140:
                description = description[:137].rsplit(" ", 1)[0] + "…"
            detail = f"{location}  ·  {description}" if description else location
            button = ctk.CTkButton(
                self.library,
                text=f"{result.title}\n{detail}",
                height=52,
                anchor="w",
                font=theme.font(12),
                text_color=theme.TEXT,
                fg_color=theme.SURFACE_ALT if index == self._selected_index else "transparent",
                hover_color=theme.SURFACE_ALT,
                border_color=theme.ACCENT,
                border_width=1 if index == self._selected_index else 0,
                command=lambda selected=result: self._choose(selected),
            )
            button._text_label.configure(justify="left")
            button.grid(row=index, column=0, sticky="ew", padx=3, pady=2)
            self._result_buttons.append(button)
        remaining = len(self.results) - end
        if remaining:
            self._more_button = ctk.CTkButton(
                self.library,
                text=f"Show {min(RESULT_BATCH_SIZE, remaining)} more ({remaining} remaining)",
                height=30,
                font=theme.font(11),
                fg_color="transparent",
                text_color=theme.ACCENT,
                hover_color=theme.SURFACE_ALT,
                command=self._append_results,
            )
            self._more_button.grid(row=end, column=0, sticky="ew", padx=3, pady=4)
        self._wrap_results()

    def _move(self, step: int) -> str:
        was_visible = self._visible
        if self._search_after is not None or not was_visible:
            self.refresh_results()
        if self.results:
            previous = self._selected_index
            self._selected_index = (
                (self._selected_index + step) % len(self.results)
                if was_visible
                else (0 if step > 0 else len(self.results) - 1)
            )
            while self._selected_index >= len(self._result_buttons):
                self._append_results()
            if 0 <= previous < len(self._result_buttons):
                self._result_buttons[previous].configure(fg_color="transparent", border_width=0)
            self._result_buttons[self._selected_index].configure(
                fg_color=theme.SURFACE_ALT, border_width=1
            )
            self._cancel("_reveal_after")
            self._reveal_after = self.after(80, self._reveal_selected)
        return "break"

    def _activate(self) -> str:
        if self._search_after is not None or not self._visible:
            self.refresh_results()
        if 0 <= self._selected_index < len(self.results):
            self._choose(self.results[self._selected_index])
        return "break"

    def _choose(self, result: SearchResult) -> None:
        self.close_results()
        self.on_select(result)

    def _escape(self) -> str:
        self.close_results()
        return "break"

    def _reveal_selected(self) -> None:
        self._reveal_after = None
        if not self._visible or self._selected_index < 0:
            return
        canvas = self.library._parent_canvas
        button = self._result_buttons[self._selected_index]
        content_height = max(1, self.library.winfo_height())
        top = button.winfo_y()
        bottom = top + button.winfo_height()
        visible_top = canvas.canvasy(0)
        visible_bottom = visible_top + canvas.winfo_height()
        if top < visible_top:
            canvas.yview_moveto(top / content_height)
        elif bottom > visible_bottom:
            canvas.yview_moveto((bottom - canvas.winfo_height()) / content_height)

    def _configured(self, event) -> None:
        if self._visible and event.widget in (self._top, self) and self._position_after is None:
            self._position_after = self.after_idle(self._position_popup)

    def _position_popup(self) -> None:
        self._position_after = None
        if not self._alive or not self._visible:
            return
        x = self.winfo_rootx() - self._top.winfo_rootx()
        y = self.winfo_rooty() - self._top.winfo_rooty() + self.winfo_height() + 3
        available = max(100, self._top.winfo_height() - y - 12)
        desired = 110 if not self.results else 68 + min(len(self.results), 6) * 56
        # Native coordinates already include CTk's scaling. Calling Tk's geometry
        # manager directly avoids applying that scale twice on high-DPI displays.
        tk.Place.place_configure(
            self.popup,
            x=x,
            y=y,
            width=self.winfo_width(),
            height=min(available, desired),
        )
        self.popup.lift()
        self._wrap_results()

    def _wrap_results(self) -> None:
        width = max(160, self.winfo_width() - 65)
        self.empty_label.configure(wraplength=width)
        for button in self._result_buttons:
            button._text_label.configure(wraplength=width)

    def _outside_click(self, event) -> None:
        if not self._visible:
            return
        widget = event.widget
        while widget is not None:
            if widget in (self, self.popup):
                return
            widget = getattr(widget, "master", None)
        self.close_results()

    def _cancel(self, attribute: str) -> None:
        ident = getattr(self, attribute)
        if ident is not None:
            self.after_cancel(ident)
            setattr(self, attribute, None)

    def _dispose(self) -> None:
        self._alive = False
        for attribute in ("_search_after", "_position_after", "_reveal_after"):
            self._cancel(attribute)
        for sequence, ident in self._top_bindings:
            self._top.unbind(sequence, ident)
        self._top_bindings.clear()
        self.popup.destroy()
