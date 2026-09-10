"""Fieldbook Workshop: application setup, maintenance and help in focused sections."""

from __future__ import annotations

import os
import platform
from tkinter import messagebox

import customtkinter as ctk

from firestone_bot import __version__, daily
from firestone_bot.gui import theme
from firestone_bot.gui.automation_catalog import WORKSHOP_GROUPS
from firestone_bot.gui.catalog import OPTIONS, READ_ONLY_LABELS, format_ahk_stamp
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.help_text import HOME_SECTIONS, SHORTCUTS, WHERE_THINGS_ARE
from firestone_bot.gui.search_catalog import SEARCH_TARGETS
from firestone_bot.gui.widgets import (
    Card,
    ReadOnlyValue,
    autowrap,
    page_frame,
    place_card,
    register_cleanup,
    reveal_widget,
)
from firestone_bot.stats import KEYS as STAT_KEYS
from firestone_bot.stats import average_cycle_ms, cycles_total, fmt_ms


class Workshop:
    """Keep each editor alive so changing sections retains its controls and scroll position."""

    def __init__(self, parent, ctx: PageContext) -> None:
        self.ctx = ctx
        self.widget = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        self.widget.grid_columnconfigure(0, weight=1)
        self.widget.grid_rowconfigure(2, weight=1)
        self.panels: dict[str, object] = {}
        self.buttons: dict[str, object] = {}
        self.controls: dict[str, object] = {}
        self.actions: dict[str, object] = {}
        self.targets: dict[str, object] = {}
        self._traces: list[tuple[object, str]] = []
        self._unsubscribes = []
        self._columns = 0
        self.section = ""
        register_cleanup(self.widget, self._destroy)

        header = ctk.CTkFrame(self.widget, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 16))
        ctk.CTkLabel(
            header,
            text="APPLICATION & RUNTIME",
            anchor="w",
            text_color=theme.ACCENT,
            font=theme.font(11, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="The workshop.",
            anchor="w",
            text_color=theme.TEXT,
            font=theme.heading(32),
        ).pack(anchor="w", pady=(3, 4))
        intro = ctk.CTkLabel(
            header,
            text="Fine-tune cycle behavior and configure the application.",
            anchor="w",
            justify="left",
            text_color=theme.MUTED,
            font=theme.font(14),
        )
        intro.pack(anchor="w")
        autowrap(header, [intro], offset=4)

        self.nav = ctk.CTkFrame(self.widget, fg_color="transparent")
        self.nav.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 8))
        labels = [(group.id, group.title) for group in WORKSHOP_GROUPS]
        labels.extend((("files", "Files & app"), ("help", "Help")))
        for key, label in labels:
            self.buttons[key] = ctk.CTkButton(
                self.nav,
                text=label,
                height=34,
                width=140,
                font=theme.font(12),
                fg_color=theme.SURFACE,
                hover_color=theme.SURFACE_ALT,
                text_color=theme.TEXT,
                border_width=1,
                border_color=theme.BORDER,
                command=lambda section=key: self.open_section(section),
            )
        self.nav.bind("<Configure>", self._layout_nav, add="+")
        self._layout_nav()
        self.host = ctk.CTkFrame(self.widget, fg_color="transparent", corner_radius=0)
        self.host.grid(row=2, column=0, sticky="nsew")
        self.host.grid_columnconfigure(0, weight=1)
        self.host.grid_rowconfigure(0, weight=1)
        ctx.extras["workshop"] = self
        state = getattr(ctx.window, "gui_state", {})
        self.open_section(
            state.get("workshop_section") or ctx.extras.get("workshop_section", "session")
        )

    def _layout_nav(self, event=None) -> None:
        width = event.width if event is not None else 900
        columns = 4 if width >= 680 else 2
        if columns == self._columns:
            return
        self._columns = columns
        for column in range(4):
            self.nav.grid_columnconfigure(column, weight=1 if column < columns else 0)
        for index, button in enumerate(self.buttons.values()):
            button.grid(
                row=index // columns, column=index % columns, sticky="ew", padx=(0, 7), pady=3
            )

    def open_section(self, section: str) -> None:
        section = {"application": "files", "run_behavior": "session"}.get(section, section)
        if section not in self.buttons:
            section = "session"
        if section not in self.panels:
            self.panels[section] = self._build_section(section)
            self.panels[section].grid(row=0, column=0, sticky="nsew")
        for key, panel in self.panels.items():
            if key == section:
                panel.grid()
            else:
                panel.grid_remove()
        for key, button in self.buttons.items():
            selected = key == section
            button.configure(
                fg_color=theme.ACCENT if selected else theme.SURFACE,
                hover_color=theme.ACCENT_HOVER if selected else theme.SURFACE_ALT,
                text_color=theme.ON_ACCENT if selected else theme.TEXT,
            )
        self.section = section
        self.ctx.extras["workshop_section"] = section
        if self.ctx.window is not None:
            self.ctx.window.gui_state["workshop_section"] = section

    def reveal_target(self, key: str) -> bool:
        """Open the correct panel and reveal a search result; never invoke it."""
        result = next(
            (
                target
                for target in SEARCH_TARGETS
                if target.page == "workshop" and target.key == key
            ),
            None,
        )
        if result is None:
            return False
        self.open_section(result.section)
        target = self.targets.get(key) or self.actions.get(key)
        if target is None and key in self.controls:
            target = self.controls[key].widget
        if target is None and key == "rollback":
            # The command only exists when the updater retained a previous installation.
            target = self.targets.get("updates")
        if target is None:
            target = self.targets.get(result.section)
        if target is None:
            return False
        reveal_widget(self.panels[self.section], target)
        return True

    def _value(self, card, key, label, getter, **kwargs):
        value = ReadOnlyValue(card.body, self.ctx, label, getter, **kwargs)
        card.add(value)
        self.targets[key] = value.widget
        return value

    def _tick(self, callback) -> None:
        def refresh():
            if self.widget.winfo_exists():
                callback()

        unsubscribe = self.ctx.register_tick(refresh)
        if callable(unsubscribe):
            self._unsubscribes.append(unsubscribe)
        refresh()

    def _trace(self, variable, callback) -> None:
        self._traces.append((variable, variable.trace_add("write", callback)))

    def _destroy(self) -> None:
        for variable, trace_id in self._traces:
            variable.trace_remove("write", trace_id)
        self._traces.clear()
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()

    def _build_section(self, section: str):
        page, content = page_frame(self.host)
        if section == "files":
            self._files(content)
        elif section == "help":
            self._help(content)
        else:
            group = next(group for group in WORKSHOP_GROUPS if group.id == section)
            card = place_card(Card(content, self.ctx, group.title, subtitle=group.summary))
            self.targets[section] = card
            for key in group.keys:
                if group.legacy:
                    # These old AHK options are retained in the INI but have no Python behavior.
                    self.ctx.binder.register(key)
                    self._value(
                        card,
                        key,
                        OPTIONS[key].label,
                        lambda name=key: self.ctx.settings.get(name) or "(empty)",
                        mono=True,
                    )
                else:
                    self.controls[key] = card.option(key)
            if section == "restart":
                self._restart_dependencies()
            elif section == "heartbeat":
                self._heartbeat(card)
            elif section == "session":
                card.note(
                    "The bot follows its existing cycle. Settings apply to the next relevant "
                    "action; changes are saved automatically when the bot is stopped."
                )
            elif section == "game":
                self._value(
                    card,
                    "LastPlatform",
                    "Store seen last",
                    lambda: self.ctx.settings.get("LastPlatform") or "Not detected yet",
                )
                card.note("Run an environment check in Camp after changing the game setup.")
                self._action(card, "environment", "Check environment", "refresh_status")
            elif section == "compatibility":
                card.note(
                    "These values remain unchanged when settings are saved. The Python bot "
                    "does not assign talent points from either field."
                )
        return page

    def _restart_dependencies(self) -> None:
        def sync(*_):
            enabled = self.controls["RestartGame"].control.var.get() == "1"
            self.controls["RestartGameTime"].set_enabled(enabled)
            self.controls["RestartGameTest"].set_enabled(enabled)

        self._trace(self.controls["RestartGame"].control.var, sync)
        sync()
        # The runner clears the one-time test after a successful test restart.

    def _heartbeat(self, card: Card) -> None:
        self._value(
            card,
            "ClientID",
            "Client ID",
            lambda: self.ctx.settings.get("ClientID") or "(generated on the first heartbeat)",
            copy=True,
        )
        banner = card.banner("warn", "Heartbeats are not sent without a Discord ID.", visible=False)

        def sync(*_):
            enabled = self.controls["EnableHeartbeat"].control.var.get() == "1"
            self.controls["DiscordID"].set_enabled(enabled)
            banner.set_visible(enabled and not self.controls["DiscordID"].control.var.get().strip())

        for key in ("EnableHeartbeat", "DiscordID"):
            self._trace(self.controls[key].control.var, sync)
        sync()

    def _action(self, card, key, label, callback, *, stopped=False, available=None):
        """Guard destructive/file replacement actions both visually and at invocation time."""

        def enabled():
            return (not stopped or not self.ctx.call("is_running")) and (
                available is None or available()
            )

        def invoke():
            if enabled():
                self.ctx.call(callback)

        button = ctk.CTkButton(
            card.body,
            text=label,
            command=invoke,
            height=34,
            font=theme.font(13),
            anchor="w",
        )
        card.add(button, always_enabled=True, pady=(4, 4))
        self.actions[key] = button

        def sync():
            state = "normal" if enabled() else "disabled"
            if button.cget("state") != state:
                button.configure(state=state)

        self._tick(sync)
        return button

    def _files(self, content) -> None:
        files = place_card(
            Card(
                content,
                self.ctx,
                "Settings & files",
                subtitle=(
                    "Your existing settings and state files remain in the same application folder."
                ),
            )
        )
        self.targets["files"] = files
        if not self.ctx.extras.get("settings_existed", True):
            files.banner(
                "info",
                "settings.ini was not found. Defaults are in use until the first save. "
                "You can import settings and map state from an older installation.",
            )
        for name in ("settings.ini", "MapStartState.ini", "firestone-bot.log"):
            self._value(
                files,
                name,
                name,
                lambda filename=name: os.path.join(self.ctx.base_dir, filename),
                mono=True,
            )
        self._action(files, "save", "Save settings now", "save_now")
        self._action(files, "reload", "Reload settings from disk", "reload", stopped=True)
        self._action(
            files, "import", "Import settings from another folder…", "import_settings", stopped=True
        )
        self._action(files, "folder", "Open settings folder", "open_folder")
        self._action(files, "log", "Open log file", "open_log")
        files.note("Reload and import are available while the bot is stopped.")
        self._value(
            files, "settings_encoding", "Settings encoding", lambda: self.ctx.settings.encoding
        )

        look = place_card(Card(content, self.ctx, "Appearance"))
        look.note(
            "Choose a skin after Workshop in the header. Each skin supports the display mode below."
        )
        self.targets["appearance"] = look
        appearance = self.ctx.extras.get("appearance_var")
        if appearance is not None:
            control = ctk.CTkSegmentedButton(
                look.body,
                values=["System", "Light", "Dark"],
                variable=appearance,
                font=theme.font(13),
            )
            look.add(control, always_enabled=True)
            self.targets["appearance"] = control
        look.note("Appearance is saved in gui_state.json and does not affect screen reading.")
        self._statistics(content)
        self._counters(content)
        self._updates(content)

    def _statistics(self, content) -> None:
        card = place_card(Card(content, self.ctx, "Cycle statistics"))
        settings = self.ctx.settings
        for key, label, getter in (
            ("CyclesTotal", "Completed cycles", lambda: str(cycles_total(settings))),
            ("LastCycleMs", "Last cycle", lambda: fmt_ms(settings.get("LastCycleMs"))),
            ("average_cycle", "Average cycle", lambda: fmt_ms(average_cycle_ms(settings))),
            ("CycleMsTotal", "Total time in cycles", lambda: fmt_ms(settings.get("CycleMsTotal"))),
        ):
            self._value(card, key, label, getter)
        card.note("Time spent inside completed cycles, retained between launches.")
        (button,) = card.buttons(("Reset cycle statistics…", self.reset_statistics))
        self.actions["reset_statistics"] = button

        def sync():
            button.configure(state="disabled" if self.ctx.call("is_running") else "normal")

        self._tick(sync)

    def reset_statistics(self) -> None:
        if self.ctx.call("is_running"):
            return
        if not messagebox.askyesno(
            "Reset cycle statistics",
            "Clear all recorded cycle counts and durations?",
            parent=self.ctx.root,
        ) or self.ctx.call("is_running"):
            return
        for key in STAT_KEYS:
            self.ctx.settings.set(key, "0")
        self.ctx.call("save_now")

    def _counters(self, content) -> None:
        card = place_card(
            Card(
                content,
                self.ctx,
                "Daily counters",
                subtitle=(
                    "Live values saved by the bot. The daily shop detects the start of a new game day."
                ),
            )
        )
        settings = self.ctx.settings
        for key in ("TokenCountDaily", "ChaosCountDaily", "ScarabCountDaily", "CrystalCountDaily"):
            self._value(
                card, key, READ_ONLY_LABELS[key], lambda name=key: settings.get(name) or "0"
            )
        for key, label, getter in (
            ("ArenaDoneDaily", "Arena completed today", daily.arena_done),
            ("ChaosBooksDaily", "Chaos books purchased today", daily.books_done),
            ("MailSweepDaily", "Mailbox swept today", daily.mail_swept),
        ):
            self._value(card, key, label, lambda getter=getter: "Yes" if getter(settings) else "No")
        for key in ("LastTokenReset", "LastChaosReset"):
            self._value(
                card,
                key,
                READ_ONLY_LABELS[key],
                lambda name=key: format_ahk_stamp(settings.get(name)),
            )
        self.reset_button = ctk.CTkButton(
            card.body,
            text="Reset daily counters…",
            command=self.reset_counters,
            height=34,
            font=theme.font(13),
            anchor="w",
        )
        card.add(self.reset_button, always_enabled=True)
        self.actions["reset"] = self.reset_button
        card.note("Use only if the automatic daily reset was missed. Available while stopped.")

        def sync():
            state = "disabled" if self.ctx.call("is_running") else "normal"
            if self.reset_button.cget("state") != state:
                self.reset_button.configure(state=state)

        self._tick(sync)

    def reset_counters(self) -> None:
        if self.ctx.call("is_running"):
            return
        if not messagebox.askyesno(
            "Reset daily counters",
            "Clear today's tavern token, chaos, scarab and crystal counters, and reset the "
            "arena, chaos-book and mailbox markers?",
            parent=self.ctx.root,
        ):
            return
        if self.ctx.call("is_running"):
            return
        try:
            daily.mark_daily_reset(self.ctx.settings)
        except OSError as error:
            messagebox.showerror(
                "Reset failed",
                f"Counters were cleared in memory, but settings.ini could not be written:\n{error}",
                parent=self.ctx.root,
            )

    def _updates(self, content) -> None:
        card = place_card(Card(content, self.ctx, "Application updates"))
        self.targets["updates"] = card
        card.note(f"Firestone Bot {__version__}")
        self.update_label = card.note(
            "The bot checks the project's GitHub releases at startup and once a day."
        )
        self._action(card, "check_update", "Check for updates now", "check_updates")
        install = self._action(
            card,
            "install_update",
            "Install available update",
            "install_update",
            stopped=True,
            available=lambda: bool(getattr(self.ctx.window, "update_button", None)),
        )
        previous = self.ctx.extras.get("previous_version")
        if previous:
            card.note(
                f"Previous version: {previous}. Restoring it restarts the application and "
                "keeps settings.ini."
            )
            self._action(
                card,
                "rollback",
                f"Restore previous version ({previous})",
                "rollback_update",
                stopped=True,
            )

        def sync():
            text = getattr(self.ctx.window, "update_text", "") or (
                "The bot checks the project's GitHub releases at startup and once a day."
            )
            label = getattr(self.ctx.window, "update_button", None) or "Install available update"
            if self.update_label.cget("text") != text:
                self.update_label.configure(text=text)
            if install.cget("text") != label:
                install.configure(text=label)

        self._tick(sync)

    def _help(self, content) -> None:
        requirements = place_card(Card(content, self.ctx, "Requirements"))
        self.targets["help"] = self.targets["requirements"] = requirements
        for title, body in HOME_SECTIONS:
            title_label = ctk.CTkLabel(
                requirements.body,
                text=title,
                anchor="w",
                text_color=theme.TEXT,
                font=theme.font(14, "bold"),
            )
            requirements.add(title_label, always_enabled=True, pady=(12, 2))
            self.targets[f"help:{title}"] = title_label
            requirements.note(body)
        navigation = place_card(Card(content, self.ctx, "Find your way"))
        self.targets["navigation"] = navigation
        navigation.note(WHERE_THINGS_ARE)
        shortcuts = place_card(Card(content, self.ctx, "Keyboard shortcuts"))
        self.targets["shortcuts"] = shortcuts
        for combo, action in SHORTCUTS:
            shortcuts.note(f"{combo}  —  {action}")
        about = place_card(Card(content, self.ctx, "About"))
        self.targets["about"] = about
        about.note(
            f"Firestone Bot {__version__} · Python {platform.python_version()} · "
            f"customtkinter {ctk.__version__}"
        )
        about.note(
            "Firestone Bot interface. Skins change appearance; automation behavior stays the same."
        )


def build(parent, ctx: PageContext):
    return Workshop(parent, ctx).widget
