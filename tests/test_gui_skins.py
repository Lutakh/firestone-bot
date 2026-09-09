"""Skin rebuilds preserve readability and release callbacks owned by old views."""

import tkinter as tk
from types import SimpleNamespace

import pytest

ctk = pytest.importorskip("customtkinter")

from firestone_bot.gui import theme, widgets
from firestone_bot.gui.binding import Binder
from firestone_bot.gui.context import PageContext
from firestone_bot.settings import Settings


@pytest.fixture(autouse=True)
def restore_skin():
    previous = theme.current_skin()
    yield
    theme.set_skin(previous)


def _contrast(first, second):
    def luminance(colour):
        channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


@pytest.mark.parametrize("name", theme.SKIN_NAMES)
def test_skin_installs_complete_readable_defaults(name):
    theme.set_skin(name)
    assert theme.current_skin() == name
    defaults = ctk.ThemeManager.theme
    assert defaults["CTk"]["fg_color"] == theme.PAPER
    assert defaults["CTkEntry"]["fg_color"] == theme.INPUT_BG
    assert defaults["CTkTextbox"]["text_color"] == theme.TEXT
    assert defaults["CTkButton"]["text_color"] == theme.ON_ACCENT
    assert defaults["DropdownMenu"]["fg_color"] == theme.SURFACE
    assert defaults["CTkFont"]["family"] == theme.FONT_FAMILY
    # Both appearance modes must remain usable, including native dropdowns.
    for foreground, background in (
        (theme.TEXT, theme.SURFACE),
        (theme.TEXT, theme.INPUT_BG),
        (theme.ON_HEADER, theme.HEADER),
        (theme.ON_ACCENT, theme.ACCENT),
    ):
        assert len(foreground) == len(background) == 2
        assert all(_contrast(fg, bg) >= 4.5 for fg, bg in zip(foreground, background))


def test_invalid_skin_leaves_current_defaults_intact():
    theme.set_skin("Retro")
    before = dict(ctk.ThemeManager.theme["CTkButton"])
    with pytest.raises(ValueError, match="Unknown interface skin"):
        theme.set_skin("unknown")
    assert theme.current_skin() == "Retro"
    assert ctk.ThemeManager.theme["CTkButton"] == before


def test_font_cache_belongs_to_current_interpreter(monkeypatch):
    monkeypatch.setattr(theme, "_fonts", {})
    monkeypatch.setattr(theme, "_font_root", None)
    monkeypatch.setattr(ctk, "CTkFont", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(tk, "_default_root", object())
    first = theme.font(14)
    assert theme.font(14) is first
    monkeypatch.setattr(tk, "_default_root", object())
    assert theme.font(14) is not first
    theme.set_skin("Fieldbook")
    assert theme.heading().family == "Georgia"
    theme.set_skin("Retro")
    assert theme.heading().family == "Courier New"
    assert theme.mono().family == theme.MONO_FAMILY


@pytest.mark.parametrize("tk9", [False, True])
def test_option_menu_skips_nested_idle_only_on_tk9(monkeypatch, tk9):
    """Regression: nested idle draws caused 230k Configure callbacks per page."""
    flushed, painted = [], []
    menu = widgets.OptionMenu.__new__(widgets.OptionMenu)
    menu._canvas = SimpleNamespace(update_idletasks=lambda: flushed.append(True))

    def draw(self, no_color_updates=False):
        self._canvas.update_idletasks()
        painted.append(True)

    monkeypatch.setattr(widgets, "MAC_TK9", tk9)
    monkeypatch.setattr(ctk.CTkOptionMenu, "_draw", draw)
    menu._draw()
    assert painted == [True]
    assert flushed == ([] if tk9 else [True])


@pytest.fixture(scope="module")
def root():
    try:
        root = ctk.CTk()
    except tk.TclError as error:
        pytest.skip(f"No native display: {error}")
    root.geometry("760x620")
    yield root
    root.destroy()


def _context(root, tmp_path):
    settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    binder = Binder(settings, root, lambda *_: None)
    ticks = []

    def register_tick(callback):
        ticks.append(callback)
        return lambda: ticks.remove(callback) if callback in ticks else None

    context = PageContext(settings, binder, {}, lambda _: None, str(tmp_path), register_tick, root)
    return context, ticks


def test_destroyed_controls_release_traces_reload_hooks_and_ticks(root, tmp_path):
    ctx, ticks = _context(root, tmp_path)
    for key in ("Alch", "MapMode", "DiscordID"):
        ctx.binder.var(key)
    core_traces = {key: len(var.trace_info()) for key, (var, _) in ctx.binder._vars.items()}
    shell = ctk.CTkFrame(root)
    shell.pack(fill="both", expand=True)
    card = widgets.Card(shell, ctx, "Alchemy", master="Alch")
    card.pack(fill="x")
    choice = widgets.Choice(card.body, ctx, "MapMode", ["detect", "coords"])
    choice.widget.pack()
    text = widgets.TextField(card.body, ctx, "DiscordID", pattern=r"^\d*$")
    text.widget.pack()
    order = widgets.OrderedList(card.body, ctx, ["1", "2", "3", "4"], key="ChaosGuardianOrder")
    order.widget.pack()
    readonly = widgets.ReadOnlyValue(card.body, ctx, "File", lambda: ctx.settings.path)
    readonly.widget.pack()
    assert ctx.binder._reload_hooks and ticks
    root.update_idletasks()
    shell.destroy()
    assert not ctx.binder._reload_hooks and not ticks
    assert not root._wrap_callbacks
    for key, count in core_traces.items():
        assert len(ctx.binder.var(key).trace_info()) == count
    # Old views must not receive writes after rebuilding a skin.
    ctx.binder.var("MapMode").set("coords")
    ctx.binder.var("DiscordID").set("123")
    ctx.binder.var("Alch").set("0")
    ctx.binder.flush()


def test_scrollable_views_release_global_bindings_and_timers(root):
    events = ("<MouseWheel>", "<KeyPress-Shift_L>", "<KeyRelease-Shift_R>")
    before = {event: root.bind_all(event) for event in events}
    for _ in range(3):
        shell = ctk.CTkFrame(root)
        shell.pack(fill="both", expand=True)
        page, content = widgets.page_frame(shell)
        page.pack(fill="both", expand=True)
        widgets.page_title(content, "A disposable view", "Long help text " * 25)
        for row in range(15):
            ctk.CTkLabel(content, text=f"Row {row}").pack()
        root.update_idletasks()
        shell.destroy()
        assert not root._wrap_callbacks
        assert {event: root.bind_all(event) for event in events} == before
    root.update()


def test_compact_option_controls_stay_inline(root, tmp_path):
    ctx, _ = _context(root, tmp_path)
    shell = ctk.CTkFrame(root, width=570)
    shell.pack()
    shell.pack_propagate(False)
    row = widgets.OptionRow(
        shell, "Collect results", "A real setting", lambda p: widgets.Switch(p, ctx, "Alch")
    )
    row.widget.pack(fill="x")
    root.update_idletasks()
    assert int(row.holder.grid_info()["row"]) == 0
    shell.destroy()
