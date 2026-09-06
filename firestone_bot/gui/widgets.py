"""Shared customtkinter widgets: cards, option rows and the bound controls.

Every control wraps one customtkinter widget, exposes `set_enabled(bool)` for card greying and
writes through the Binder (`ctx.binder`). Icons are text glyphs only (no CTkImage / PIL).
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from firestone_bot.gui import catalog, theme
from firestone_bot.gui.catalog import INVERTED_KEYS, OPTIONS, SELL_PRECEDENCE, Option
from firestone_bot.gui.context import PageContext

SWITCH_WIDTH = 50
MENU_WIDTH = 220
NUMBER_WIDTH = 80
HELP_WRAP = 520


def assets_dir() -> str:
    """Folder of the bundled images: assets/ in the source tree, _internal/assets (or
    Contents/Resources/assets) in a PyInstaller build."""
    import os

    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "assets")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets"
    )


def _state(enabled: bool) -> str:
    return "normal" if enabled else "disabled"


def bind_platform_wheel(scrollable: ctk.CTkScrollableFrame) -> None:
    """Wheel scrolling customtkinter does not handle: <Button-4>/<Button-5> on X11, and on
    macOS with Tk 9 the trackpad's <TouchpadScroll> (pixel deltas, no <MouseWheel> at all)
    plus <MouseWheel> deltas that are now multiples of 120 (ctk scrolls 120 units per notch).
    macOS with Tk 8.6: ctk's handler is kept (see MAC_TK9)."""
    canvas = scrollable._parent_canvas

    def mine(event) -> bool:
        return scrollable.check_if_master_is_canvas(event.widget)

    if sys.platform.startswith("linux"):

        def scroll(event):
            if mine(event):
                canvas.yview("scroll", -1 if event.num == 4 else 1, "units")

        scrollable.bind_all("<Button-4>", scroll, add="+")
        scrollable.bind_all("<Button-5>", scroll, add="+")
    elif sys.platform == "darwin" and MAC_TK9:
        scrollable._mouse_wheel_all = lambda event: None  # ctk's 120-units-per-notch handler
        acc = [0.0]

        def wheel(event):  # ctk's own handler is neutralised at import, see below
            if mine(event) and canvas.yview() != (0.0, 1.0):
                notches = int(event.delta / 120) or (1 if event.delta > 0 else -1)
                canvas.yview("scroll", -notches * WHEEL_UNITS_PER_NOTCH, "units")

        def touchpad(event):
            if not mine(event) or canvas.yview() == (0.0, 1.0):
                return
            _dx, dy = scrollable.tk.call("tk::PreciseScrollDeltas", event.delta)
            acc[0] += float(dy) / TOUCHPAD_PIXELS_PER_UNIT
            units = int(acc[0])
            if units:
                acc[0] -= units
                canvas.yview("scroll", -units, "units")

        scrollable.bind_all("<MouseWheel>", wheel, add="+")
        scrollable.bind_all("<TouchpadScroll>", touchpad, add="+")


TOUCHPAD_PIXELS_PER_UNIT = 6  # trackpad pixels per canvas scroll unit (feel, not geometry)
WHEEL_UNITS_PER_NOTCH = 20  # what ctk scrolls per notch on Windows (delta 120 / 6)

# Tk 9 (Homebrew python-tk) changed macOS scrolling: <MouseWheel> deltas of 120 per notch
# and a separate <TouchpadScroll> event for the trackpad. Tk 8.6 (python.org / GitHub
# runners, what the packaged bundle ships) has neither: its <MouseWheel> delta is already in
# lines for wheel and trackpad alike, and ctk's own handler is right for it, so nothing is
# bound there ("bad event type or keysym TouchpadScroll" otherwise).
MAC_TK9 = sys.platform == "darwin" and tk.TkVersion >= 9.0
if MAC_TK9:
    # ctk binds its bound method at frame creation and Tk 9 reports deltas of 120 per notch,
    # so it would scroll 120 units per notch: neutralise it on the class before any frame
    # exists (bind_platform_wheel installs the replacement).
    ctk.CTkScrollableFrame._mouse_wheel_all = lambda self, event: None


CONTENT_WIDTH = 960  # page content column cap (page_frame); wrap widths derive from it


def autowrap(frame, labels, offset: int = 0, minimum: int = 120) -> None:
    """Give `labels` a wraplength fitted to `frame` once it has been laid out.

    A permanent <Configure> handler here caused an event storm (every wraplength change
    resized the label, which re-fired <Configure> on every customtkinter widget inside the
    frame). Instead the frame width is read a few times after idle until the layout has
    settled, and again once after each window resize burst.
    """
    state = {"tries": 0, "after": None}

    def apply(width: int) -> None:
        wrap = max(minimum, width - offset)
        for lbl in labels:
            if lbl.cget("wraplength") != wrap:
                lbl.configure(wraplength=wrap)

    def measure() -> None:
        state["after"] = None
        try:
            width = frame.winfo_width()
        except tk.TclError:
            return  # destroyed
        if width <= 1 and state["tries"] < 10:
            state["tries"] += 1
            state["after"] = frame.after(100, measure)
            return
        if width > 1:
            apply(width)

    def on_resize(_event) -> None:
        # coalesce the burst of <Configure> events of a resize into one measurement
        if state["after"] is None:
            state["after"] = frame.after(150, measure)

    frame.after_idle(measure)
    top = frame.winfo_toplevel()
    top.bind("<Configure>", on_resize, add="+")


# -- base control -------------------------------------------------------------------------------
class Control:
    widget: ctk.CTkBaseClass
    note: tuple[str, str] | None = None  # (kind, text) shown in the row's help line at build
    note_cb: Callable[[str | None, str | None], None] | None = None

    def set_enabled(self, enabled: bool) -> None:
        self.widget.configure(state=_state(enabled))

    def _notify(self, kind: str | None, text: str | None) -> None:
        self.note = (kind, text) if kind else None
        if self.note_cb:
            self.note_cb(kind, text)


class Switch(Control):
    def __init__(self, parent, ctx: PageContext, name: str, inverted: bool | None = None) -> None:
        if inverted is None:
            inverted = name in INVERTED_KEYS
        self.name = name
        self.var = ctx.binder.var(name, inverted)
        self.widget = ctk.CTkSwitch(
            parent, text="", variable=self.var, onvalue="1", offvalue="0", width=SWITCH_WIDTH
        )

    def is_on(self) -> bool:
        return self.var.get() == "1"


class Check(Control):
    def __init__(self, parent, ctx: PageContext, name: str, label: str | None = None) -> None:
        self.var = ctx.binder.var(name, name in INVERTED_KEYS)
        self.widget = ctk.CTkCheckBox(
            parent,
            text=label if label is not None else OPTIONS[name].label,
            variable=self.var,
            onvalue="1",
            offvalue="0",
            font=theme.font(13),
        )


class _Picker(Control):
    """Common part of Choice and Segmented: value <-> display label, unknown stored values."""

    def __init__(
        self,
        ctx: PageContext,
        name: str,
        values,
        display: dict[str, str] | None,
        unknown_note: tuple[str, str] | None,
    ) -> None:
        self.var = ctx.binder.var(name)
        self.values = list(values)
        self.display = dict(display or {})
        stored = self.var.get()
        self.unknown = None if stored in self.values else stored
        labels = [self.display.get(v, v) for v in self.values]
        if self.unknown is not None:
            labels.insert(0, f"(unknown) {self.unknown}")
            self.note = unknown_note or (
                "warn",
                (
                    f"settings.ini has {self.unknown!r}: not one of the choices. Pick one to "
                    "replace it."
                ),
            )
        self.labels = labels
        self._by_label = {lbl: v for lbl, v in zip(labels[-len(self.values) :], self.values)}
        if self.unknown is not None:
            self._by_label[labels[0]] = self.unknown
        self.var.trace_add("write", lambda *_: self._sync())

    def label_of(self, value: str) -> str:
        if value == self.unknown:
            return f"(unknown) {value}"
        return self.display.get(value, value)

    def _chosen(self, label: str) -> None:
        value = self._by_label.get(label, label)
        if value != self.var.get():
            self.var.set(value)

    def _sync(self) -> None:
        widget = getattr(self, "widget", None)
        if widget is not None:
            widget.set(self.label_of(self.var.get()))


class Choice(_Picker):
    def __init__(
        self,
        parent,
        ctx: PageContext,
        name: str,
        values,
        display: dict[str, str] | None = None,
        unknown_note: tuple[str, str] | None = None,
        width: int = MENU_WIDTH,
    ) -> None:
        super().__init__(ctx, name, values, display, unknown_note)
        self.widget = ctk.CTkOptionMenu(
            parent, values=self.labels, command=self._chosen, width=width, font=theme.font(13)
        )
        self.widget.set(self.label_of(self.var.get()))


class Segmented(_Picker):
    def __init__(
        self,
        parent,
        ctx: PageContext,
        name: str,
        values,
        display: dict[str, str] | None = None,
        unknown_note: tuple[str, str] | None = None,
    ) -> None:
        super().__init__(ctx, name, values, display, unknown_note)
        self.widget = ctk.CTkSegmentedButton(
            parent, values=self.labels, command=self._chosen, font=theme.font(13)
        )
        self.widget.set(self.label_of(self.var.get()))


class NumberField(Control):
    """Digits-only entry; empty is allowed (daily._int treats it as 0)."""

    def __init__(self, parent, ctx: PageContext, name: str, zero_means: str | None) -> None:
        self.var = ctx.binder.var(name)
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        ok = self.frame.register(lambda s: s == "" or s.isdigit())
        self.widget = ctk.CTkEntry(
            self.frame,
            width=NUMBER_WIDTH,
            textvariable=self.var,
            justify="right",
            validate="key",
            validatecommand=(ok, "%P"),
            font=theme.font(13),
        )
        self.widget.pack(side="left")
        self.suffix = ctk.CTkLabel(
            self.frame, text=zero_means or "", text_color=theme.MUTED, font=theme.font(12)
        )
        self.suffix.pack(side="left", padx=(8, 0))
        self.live = ctk.CTkLabel(self.frame, text="", text_color=theme.INFO, font=theme.font(12))
        self.live.pack(side="left", padx=(8, 0))

    def set_live(self, text: str) -> None:
        if self.live.cget("text") != text:
            self.live.configure(text=text)


class TextField(Control):
    def __init__(
        self,
        parent,
        ctx: PageContext,
        name: str,
        pattern: str | None = None,
        width: int = MENU_WIDTH,
    ) -> None:
        self.var = ctx.binder.var(name)
        self.pattern = pattern
        self.widget = ctk.CTkEntry(parent, width=width, textvariable=self.var, font=theme.font(13))
        self._normal_border = self.widget.cget("border_color")
        self.var.trace_add("write", lambda *_: self._validate())
        self._validate()

    def _validate(self) -> None:
        good = catalog.matches(self.pattern, self.var.get())
        self.widget.configure(border_color=self._normal_border if good else theme.ERR)
        self._notify(None if good else "warn", None if good else "Expected digits only.")


class RadioGroup(Control):
    def __init__(self, parent, ctx: PageContext, keys: list[str], labels: list[str]) -> None:
        self.ctx = ctx
        self.keys = list(keys)
        self.labels_by_key = dict(zip(self.keys, labels))
        self.var = tk.StringVar(value=self._current())
        self.widget = ctk.CTkFrame(parent, fg_color="transparent")
        self.buttons = []
        for key, label in zip(self.keys, labels):
            b = ctk.CTkRadioButton(
                self.widget,
                text=label,
                variable=self.var,
                value=key,
                command=self._changed,
                font=theme.font(13),
            )
            b.pack(anchor="w", pady=3)
            self.buttons.append(b)
        ctx.binder.register(*self.keys)
        ctx.binder.on_reload(self._load)
        if not self.var.get():
            self.note = ("warn", "No selling strategy selected in settings.ini.")

    def _current(self) -> str:
        """Active key, in the precedence order of features/exotic_merchant.py."""
        flagged = [k for k in SELL_PRECEDENCE if k in self.keys and self.ctx.settings.flag(k)]
        flagged += [k for k in self.keys if k not in SELL_PRECEDENCE and self.ctx.settings.flag(k)]
        if len(flagged) > 1:
            label = self.labels_by_key.get(flagged[0], flagged[0])
            self._notify(
                "warn",
                f"Several selling strategies are set in settings.ini; the bot uses "
                f"'{label}'. Pick one to fix it.",
            )
        return flagged[0] if flagged else ""

    def _changed(self) -> None:
        chosen = self.var.get()
        self.ctx.binder.set_many({k: "1" if k == chosen else "0" for k in self.keys})
        self._notify(None, None)

    def _load(self) -> None:
        self._notify(None, None)
        self.var.set(self._current())

    def set_enabled(self, enabled: bool) -> None:
        for b in self.buttons:
            b.configure(state=_state(enabled))


class LinkButton:
    def __init__(self, parent, text: str, command, kind: str = "info") -> None:
        self.widget = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color="transparent",
            hover=False,
            text_color=theme.colour(kind),
            font=theme.font(12),
            height=22,
            width=0,
            anchor="w",
        )

    def set_enabled(self, enabled: bool) -> None:
        self.widget.configure(state=_state(enabled))


class CheckGrid(Control):
    def __init__(
        self,
        parent,
        ctx: PageContext,
        items: list[tuple[str, str]],
        columns: int = 3,
        heading: str | None = None,
        links: bool = True,
    ) -> None:
        self.ctx = ctx
        self.keys = [k for k, _ in items]
        self.widget = ctk.CTkFrame(parent, fg_color="transparent")
        top = ctk.CTkFrame(self.widget, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=columns, sticky="ew")
        if heading:
            ctk.CTkLabel(top, text=heading, font=theme.font(13, "bold")).pack(side="left")
        self.links: list[LinkButton] = []
        if links:
            for text, value in (("None", "0"), ("All", "1")):
                lb = LinkButton(top, text, lambda v=value: self._set_all(v))
                lb.widget.pack(side="right", padx=(6, 0))
                self.links.append(lb)
        self.checks: list[Check] = []
        for i, (key, label) in enumerate(items):
            c = Check(self.widget, ctx, key, label)
            c.widget.grid(row=1 + i // columns, column=i % columns, sticky="w", padx=4, pady=3)
            self.checks.append(c)
        for c in range(columns):
            self.widget.grid_columnconfigure(c, weight=1, uniform="cg")

    def _set_all(self, value: str) -> None:
        self.ctx.binder.set_many(dict.fromkeys(self.keys, value))

    def set_enabled(self, enabled: bool) -> None:
        for c in self.checks:
            c.set_enabled(enabled)
        for lb in self.links:
            lb.set_enabled(enabled)


class OrderedList(Control):
    """N rows `1. <name> [▲] [▼]` writing either N keys or one comma-separated key."""

    def __init__(
        self,
        parent,
        ctx: PageContext,
        choices,
        keys: list[str] | None = None,
        key: str | None = None,
        sep: str = ",",
        display: dict[str, str] | None = None,
        row_labels: list[str] | None = None,
    ) -> None:
        self.ctx = ctx
        self.choices = list(choices)
        self.keys = list(keys or [])
        self.key = key
        self.sep = sep
        self.display = dict(display or {})
        self.row_labels = row_labels
        self.widget = ctk.CTkFrame(parent, fg_color="transparent")
        self.widget.grid_columnconfigure(0, weight=1)
        self.banner = Banner(self.widget, "warn", "")
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.banner.set_visible(False)
        self.rows = ctk.CTkFrame(self.widget, fg_color="transparent")
        self.rows.grid(row=1, column=0, sticky="ew")
        self.rows.grid_columnconfigure(0, weight=1)
        self.labels: list[ctk.CTkLabel] = []
        self.buttons: list[ctk.CTkButton] = []
        for i in range(len(self.choices)):
            lbl = ctk.CTkLabel(self.rows, text="", anchor="w", font=theme.font(13))
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            up = ctk.CTkButton(
                self.rows, text="▲", width=32, height=26, command=lambda i=i: self._move(i, -1)
            )
            down = ctk.CTkButton(
                self.rows, text="▼", width=32, height=26, command=lambda i=i: self._move(i, 1)
            )
            up.grid(row=i, column=1, padx=(6, 2))
            down.grid(row=i, column=2, padx=(2, 0))
            self.labels.append(lbl)
            self.buttons += [up, down]
        ctx.binder.register(*(self.keys or [key]))
        ctx.binder.on_reload(self._load)
        self._enabled = True
        self._load()

    # -- model -------------------------------------------------------------------------------
    def _stored(self) -> list[str]:
        if self.key:
            return [v.strip() for v in self.ctx.settings.get(self.key).split(self.sep)]
        return [self.ctx.settings.get(k).strip() for k in self.keys]

    def _load(self) -> None:
        stored = self._stored()
        self.valid = catalog.is_permutation(stored, self.choices)
        self.order = stored if self.valid else list(self.choices)
        if self.valid:
            self.banner.set_visible(False)
        else:
            shown = self.sep.join(stored) if self.key else ", ".join(stored)
            self.banner.set_text(f"settings.ini has {shown}: not a valid order. Use ▲/▼ to fix it.")
            self.banner.set_visible(True)
        self._render()

    def _render(self) -> None:
        for i, (lbl, value) in enumerate(zip(self.labels, self.order)):
            prefix = self.row_labels[i] if self.row_labels else f"{i + 1}."
            lbl.configure(
                text=f"{prefix}  {self.display.get(value, value)}",
                text_color=theme.MUTED if not self.valid else ("gray10", "gray90"),
            )
        n = len(self.order)
        for i, b in enumerate(self.buttons):
            row, is_down = divmod(i, 2)
            edge = (row == n - 1) if is_down else (row == 0)
            b.configure(state=_state(self._enabled and not edge))

    def _move(self, i: int, delta: int) -> None:
        j = i + delta
        if not (0 <= j < len(self.order)):
            return
        self.order[i], self.order[j] = self.order[j], self.order[i]
        self.valid = True
        self.banner.set_visible(False)
        self._write()
        self._render()

    def _write(self) -> None:
        if self.key:
            self.ctx.binder.set_many({self.key: self.sep.join(self.order)})
        else:
            self.ctx.binder.set_many(dict(zip(self.keys, self.order)))

    def reset(self, order: list[str]) -> None:
        self.order = list(order)
        self.valid = True
        self.banner.set_visible(False)
        self._write()
        self._render()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._render()


class ReadOnlyValue:
    """Label + value refreshed by the tick, optional Copy button."""

    def __init__(
        self,
        parent,
        ctx: PageContext,
        label: str,
        getter: Callable[[], str],
        copy: bool = False,
        mono: bool = False,
    ) -> None:
        self.getter = getter
        self.widget = ctk.CTkFrame(parent, fg_color="transparent")
        self.widget.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.widget, text=label, anchor="w", font=theme.font(13), width=200).grid(
            row=0, column=0, sticky="w"
        )
        self.value = ctk.CTkLabel(
            self.widget,
            text="",
            anchor="w",
            justify="left",
            wraplength=HELP_WRAP,
            text_color=theme.MUTED,
            font=theme.font(12, family=theme.MONO_FAMILY if mono else theme.FONT_FAMILY),
        )
        self.value.grid(row=0, column=1, sticky="w", padx=(12, 0))
        if copy:
            ctk.CTkButton(self.widget, text="Copy", width=60, height=26, command=self._copy).grid(
                row=0, column=2, padx=(8, 0)
            )
        self.refresh()
        ctx.register_tick(self.refresh)

    def refresh(self) -> None:
        text = self.getter()
        if self.value.cget("text") != text:
            self.value.configure(text=text)

    def _copy(self) -> None:
        self.widget.clipboard_clear()
        self.widget.clipboard_append(self.getter())

    def set_enabled(self, enabled: bool) -> None:  # read-only: nothing to grey
        pass


class Banner(ctk.CTkFrame):
    """Full-width coloured strip (grid-managed; `set_visible` uses grid/grid_remove)."""

    def __init__(
        self,
        parent,
        kind: str,
        text: str,
        action_label: str | None = None,
        action: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color=theme.BANNER_BG.get(kind, theme.BANNER_BG["info"]))
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(
            self,
            text=text,
            text_color=theme.colour(kind),
            font=theme.font(12),
            anchor="w",
            justify="left",
            wraplength=HELP_WRAP,
        )
        self.label.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self.button = None
        if action_label:
            self.button = ctk.CTkButton(
                self, text=action_label, width=90, height=26, command=action
            )
            self.button.grid(row=0, column=1, padx=(8, 12), pady=6)
        self._visible = True

    def set_text(self, text: str) -> None:
        if self.label.cget("text") != text:
            self.label.configure(text=text)

    def set_visible(self, visible: bool) -> None:
        if visible == self._visible:
            return
        self._visible = visible
        if visible:
            self.grid()
        else:
            self.grid_remove()

    def set_enabled(self, enabled: bool) -> None:
        pass


class StatusDot:
    def __init__(self, parent, kind: str = "grey", size: int = 14) -> None:
        self.widget = ctk.CTkLabel(
            parent, text="●", text_color=theme.colour(kind), font=theme.font(size), width=16
        )
        self.kind = kind

    def set(self, kind: str) -> None:
        if kind != self.kind:
            self.kind = kind
            self.widget.configure(text_color=theme.colour(kind))


class Meter:
    """Name, `used / limit` and a progress bar (hidden when there is no limit)."""

    def __init__(self, parent, label: str) -> None:
        self.widget = ctk.CTkFrame(parent, fg_color="transparent")
        self.widget.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.widget, text=label, anchor="w", font=theme.font(13)).grid(
            row=0, column=0, sticky="w"
        )
        self.value = ctk.CTkLabel(
            self.widget, text="", anchor="e", text_color=theme.MUTED, font=theme.font(12)
        )
        self.value.grid(row=0, column=1, sticky="e")
        self.bar = ctk.CTkProgressBar(self.widget, height=8)
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        self._bar_shown = True
        self._text = None
        self.set(0, 0)

    def set(self, used: int, limit: int) -> None:
        if limit <= 0:
            text = f"{used} used, no limit"
            if self._bar_shown:
                self.bar.grid_remove()
                self._bar_shown = False
        else:
            text = f"{used} / {limit}"
            if not self._bar_shown:
                self.bar.grid()
                self._bar_shown = True
            ratio = min(1.0, used / limit)
            self.bar.set(ratio)
            kind = "err" if ratio >= 1.0 else "warn" if ratio >= 0.8 else "ok"
            self.bar.configure(progress_color=theme.colour(kind))
        if text != self._text:
            self._text = text
            self.value.configure(text=text)


class StatePill:
    def __init__(self, parent) -> None:
        self.widget = ctk.CTkLabel(
            parent,
            text="Idle",
            corner_radius=12,
            fg_color=theme.NEUTRAL,
            text_color="white",
            font=theme.font(12, "bold"),
            padx=12,
            height=26,
        )
        self._state = ("Idle", "grey")

    def set(self, text: str, kind: str) -> None:
        if (text, kind) == self._state:
            return
        self._state = (text, kind)
        self.widget.configure(text=text, fg_color=theme.colour(kind))


# -- rows and cards -----------------------------------------------------------------------------
class OptionRow:
    """Two-column row: label + help line on the left, one control on the right."""

    def __init__(
        self,
        parent,
        label: str,
        help: str,
        make_control: Callable[[ctk.CTkBaseClass], object],
        help_kind: str = "muted",
        always_enabled: bool = False,
    ) -> None:
        self.always_enabled = always_enabled
        self.default_help = help
        self.default_kind = help_kind
        self.widget = ctk.CTkFrame(parent, fg_color="transparent")
        self.widget.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(self.widget, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew")
        self.label = ctk.CTkLabel(left, text=label, anchor="w", font=theme.font(13))
        self.label.pack(anchor="w")
        self.help = ctk.CTkLabel(
            left,
            text=help,
            anchor="w",
            justify="left",
            wraplength=HELP_WRAP,
            text_color=theme.colour(help_kind),
            font=theme.font(12),
        )
        if help:
            self.help.pack(anchor="w")
        self.holder = holder = ctk.CTkFrame(self.widget, fg_color="transparent")
        holder.grid(row=0, column=1, sticky="e", padx=(16, 0))
        self.control = make_control(holder)
        w = getattr(self.control, "frame", None)
        if w is None:
            w = getattr(self.control, "widget", self.control)
        w.pack(side="left")
        self.control_widget = w

        # The help line keeps its static HELP_WRAP: a per-row <Configure> handler adjusting it
        # re-fired layout events for the whole page (see autowrap).
        if isinstance(self.control, Control):
            self.control.note_cb = self.set_note
            if self.control.note:
                self.set_note(*self.control.note)

    def set_note(self, kind: str | None, text: str | None) -> None:
        if kind is None:
            self.help.configure(text=self.default_help, text_color=theme.colour(self.default_kind))
        else:
            self.help.configure(text=text or self.default_help, text_color=theme.colour(kind))
        if not self.help.winfo_manager():
            self.help.pack(anchor="w")

    def set_enabled(self, enabled: bool) -> None:
        if hasattr(self.control, "set_enabled"):
            self.control.set_enabled(enabled)
        self.label.configure(text_color=("gray10", "gray90") if enabled else theme.MUTED)


class Card(ctk.CTkFrame):
    """Rounded card with a title row (optional master switch) and a body of stacked rows."""

    def __init__(
        self,
        parent,
        ctx: PageContext,
        title: str,
        subtitle: str | None = None,
        master: str | None = None,
        master_help: str | None = None,
        expand: bool = False,
    ) -> None:
        super().__init__(parent, corner_radius=10)
        self.ctx = ctx
        self._items: list[tuple[object, bool]] = []
        self._row = 0
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(titles, text=title, anchor="w", font=theme.font(15, "bold")).pack(anchor="w")
        if master and master_help is None:
            master_help = OPTIONS[master].help
        text = subtitle or master_help
        if text:
            ctk.CTkLabel(
                titles,
                text=text,
                anchor="w",
                justify="left",
                wraplength=HELP_WRAP,
                text_color=theme.MUTED,
                font=theme.font(12),
            ).pack(anchor="w")
        self.master_switch: Switch | None = None
        if master:
            mrow = ctk.CTkFrame(header, fg_color="transparent")
            mrow.grid(row=0, column=1, sticky="ne", padx=(16, 0))
            ctk.CTkLabel(mrow, text=OPTIONS[master].label, font=theme.font(13)).pack(
                side="left", padx=(0, 8)
            )
            self.master_switch = Switch(mrow, ctx, master)
            self.master_switch.widget.pack(side="left")
            self.master_switch.var.trace_add("write", lambda *_: self._apply_master())
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both" if expand else "x", expand=expand, padx=16, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=1)

    # -- content -----------------------------------------------------------------------------
    def add(self, item, always_enabled: bool = False, pady=(4, 4), expand: bool = False):
        w = getattr(item, "widget", item)
        w.grid(row=self._row, column=0, sticky="nsew" if expand else "ew", pady=pady)
        if expand:
            self.body.grid_rowconfigure(self._row, weight=1)
        self._row += 1
        self._items.append((item, always_enabled))
        if self.master_switch and hasattr(item, "set_enabled") and not always_enabled:
            item.set_enabled(self.master_on())
        return item

    def option(self, key: str, always_enabled: bool = False, **kw) -> OptionRow:
        opt: Option = OPTIONS[key]
        return self.row(
            opt.label,
            opt.help,
            lambda parent: make_control(parent, self.ctx, key, opt, **kw),
            help_kind="warn" if opt.warn else "muted",
            always_enabled=always_enabled,
        )

    def row(self, label, help, make, help_kind="muted", always_enabled=False) -> OptionRow:
        r = OptionRow(self.body, label, help, make, help_kind, always_enabled)
        self.add(r, always_enabled)
        return r

    def banner(self, kind: str, text: str, action_label=None, action=None, visible=True) -> Banner:
        b = Banner(self.body, kind, text, action_label, action)
        self.add(b, always_enabled=True, pady=(4, 6))
        b.set_visible(visible)
        return b

    def note(self, text: str, kind: str = "muted", wrap: int = HELP_WRAP + 200) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            self.body,
            text=text,
            anchor="w",
            justify="left",
            wraplength=wrap,
            text_color=theme.colour(kind),
            font=theme.font(12),
        )
        self.add(lbl, always_enabled=True, pady=(2, 2))
        autowrap(self.body, [lbl], offset=8)  # never wider than the card (980 px window)
        return lbl

    def buttons(self, *specs: tuple[str, Callable[[], None]], always_enabled=True) -> list:
        f = ctk.CTkFrame(self.body, fg_color="transparent")
        out = []
        for text, cmd in specs:
            b = ctk.CTkButton(f, text=text, command=cmd, height=30, font=theme.font(13))
            b.pack(side="left", padx=(0, 8))
            out.append(b)
        self.add(f, always_enabled=always_enabled, pady=(6, 2))
        return out

    # -- master greying ----------------------------------------------------------------------
    def master_on(self) -> bool:
        return self.master_switch is None or self.master_switch.is_on()

    def _apply_master(self) -> None:
        self.set_enabled(self.master_on())

    def set_enabled(self, enabled: bool) -> None:
        for item, always in self._items:
            if not always and hasattr(item, "set_enabled"):
                item.set_enabled(enabled)


def make_control(parent, ctx: PageContext, key: str, opt: Option | None = None, **kw):
    """Build the control described by the catalog entry of `key`."""
    opt = opt or OPTIONS[key]
    if opt.kind == "switch":
        return Switch(parent, ctx, key)
    if opt.kind == "check":
        return Check(parent, ctx, key)
    if opt.kind in ("choice", "seg"):
        stored = ctx.settings.get(key)
        if "unknown_note" not in kw and stored not in opt.values:
            kw["unknown_note"] = catalog.unknown_note(key, stored)
    if opt.kind == "choice":
        values = kw.pop("values", None) or list(opt.values) or [stored]
        return Choice(parent, ctx, key, values, opt.display or None, **kw)
    if opt.kind == "seg":
        return Segmented(parent, ctx, key, list(opt.values), opt.display or None, **kw)
    if opt.kind == "num":
        return NumberField(parent, ctx, key, opt.zero_means)
    if opt.kind == "text":
        return TextField(parent, ctx, key, opt.pattern, **kw)
    raise ValueError(f"{key}: kind {opt.kind!r} needs a dedicated widget")


def page_frame(parent, scrollable: bool = True):
    """Page container: a scrollable frame with a content column capped at 960 px."""
    page = (
        ctk.CTkScrollableFrame(parent, fg_color="transparent")
        if scrollable
        else ctk.CTkFrame(parent, fg_color="transparent")
    )
    if scrollable:
        bind_platform_wheel(page)
    content = ctk.CTkFrame(page, fg_color="transparent")
    content.grid(row=0, column=0, sticky="nsew", padx=(24, 12), pady=(16, 24))
    page.grid_rowconfigure(0, weight=1)

    state = {"wide": None}

    def cap(event):
        wide = event.width > CONTENT_WIDTH + 48
        if wide == state["wide"]:
            return  # reconfiguring the grid on every event re-fires <Configure> on every child
        state["wide"] = wide
        if wide:
            page.grid_columnconfigure(0, weight=0, minsize=CONTENT_WIDTH)
            page.grid_columnconfigure(1, weight=1)
        else:
            page.grid_columnconfigure(0, weight=1, minsize=0)
            page.grid_columnconfigure(1, weight=0)

    page.grid_columnconfigure(0, weight=1)
    # add="+": CTkScrollableFrame's own <Configure> binding updates the canvas scrollregion;
    # replacing it would leave every page unscrollable (bottom rows cut off).
    page.bind("<Configure>", cap, add="+")
    return page, content


def page_title(content, title: str, subtitle: str | None = None) -> None:
    ctk.CTkLabel(content, text=title, anchor="w", font=theme.font(20, "bold")).pack(
        anchor="w", pady=(0, 2)
    )
    if subtitle:
        lbl = ctk.CTkLabel(
            content,
            text=subtitle,
            anchor="w",
            justify="left",
            wraplength=HELP_WRAP + 200,
            text_color=theme.MUTED,
            font=theme.font(12),
        )
        lbl.pack(anchor="w", pady=(0, 8))
        autowrap(content, [lbl], offset=4)


def place_card(card: Card) -> Card:
    card.pack(fill="x", pady=8)
    return card
