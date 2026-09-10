"""Automation library with one live settings editor and global-search destinations."""

from __future__ import annotations

import os
from collections.abc import Callable

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui import theme
from firestone_bot.gui.automation_catalog import (
    AUTOMATIONS,
    CATEGORIES,
    GROUPS_BY_ID,
    AutomationGroup,
    disabled_reason,
    group_status,
    matches_group,
)
from firestone_bot.gui.catalog import (
    CHAOS_GUARDIAN_CHOICES,
    HERO_TARGET_KEYS,
    INVERTED_KEYS,
    OPTIONS,
    PRIORITY_CHOICES,
    PRIORITY_KEYS,
    SELL_KEYS,
    SELL_LABELS,
    TREE_GROUPS,
    TREE_KEYS,
)
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import (
    Card,
    CheckGrid,
    OrderedList,
    RadioGroup,
    ScrollableFrame,
    bind_platform_wheel,
    reveal_widget,
)
from firestone_bot.progress import Progress
from firestone_bot.settings import SETTINGS_MAP

# These clarify cross-editor behavior without changing any saved option or runner action.
EDITOR_NOTES = {
    "daily_rewards": "The shop is visited every cycle to detect the daily reset, even when its reward switch is off.",
    "chests": "Oracle's gifts and mystery boxes use their own switches. Celestial chests also need Upgrade blessings in Oracle & blessings.",
    "guardians": "The upgrade order is used during guardian visits and after successful guild chaos-rift hits. Training uses roster positions, not guardian names.",
    "oracle": "Upgrade blessings also controls celestial chests in the bag, even when oracle visits are off. The oracle itself requires account level 200.",
    "engineer": "War machine upgrades happen inside the engineer visit. A machine and a blueprint-capable mode must be selected to edit blueprint choices.",
    "map": "Category priority is used only in Coordinates mode. Detection mode reads visible mission icons from the screen.",
    "campaign": "Campaign runs during the map visit. Dungeon missions are part of the liberation routine.",
    "guild": "Guild visits also enable the separate Hero awakening, Personal tree, Chaos rift and Arcane crystal editors.",
    "tree": "Choose upgrade targets below. These upgrades run during the guild visit.",
    "chaos": "Only free chaos tokens are spent. Available books are checked on every rift visit, including after the daily hit limit has been reached.",
    "mail": "When deletion is enabled, the mailbox is swept once per game day and all read mail is deleted. Without deletion, the bot can revisit new mail.",
    "scarab": "Pharaoh-token collection and scarab play are independent of the tavern visit switch.",
    "tavern": "Crafting is checked on every tavern visit, even when token play is off. Scarab settings have their own editor.",
    "merchant": "Selling strategies are mutually exclusive. Selecting one updates all four saved strategy flags together.",
}
RELATED_GROUPS = {
    "chests": (("Oracle & blessings", "oracle"),),
    "oracle": (("Chests & gifts", "chests"),),
    "guardians": (("Chaos rift", "chaos"),),
    "chaos": (("Guild visits", "guild"), ("Guardian training", "guardians")),
    "crystal": (("Guild visits", "guild"),),
    "tree": (("Guild visits", "guild"),),
    "awakening": (("Guild visits", "guild"),),
    "guild": (("Personal tree", "tree"), ("Chaos rift", "chaos"), ("Arcane crystal", "crystal")),
    "campaign": (("Map missions", "map"),),
    "map": (("Campaign", "campaign"),),
    "scarab": (("Tavern & artifacts", "tavern"),),
    "tavern": (("Scarab game", "scarab"),),
}
COUNTERS = {
    "MaxTokens": ("TokenCountDaily", "tokens used today"),
    "MaxScarab": ("ScarabCountDaily", "plays today"),
    "MaxChaos": ("ChaosCountDaily", "hits today"),
    "MaxCrystals": ("CrystalCountDaily", "hits today"),
}


def _help_text(key: str) -> str:
    plain_help = {
        "Alch": "Collect completed experiments and start new ones with the selected resources.",
        "DragonBlood": "Spend dragon blood on new experiments.",
        "Dust": "Spend magic dust on new experiments.",
        "Pickaxes": "Collect ready pickaxes from the guild shop.",
        "Scarab": "Play the scarab game using free tokens, up to your daily limit.",
        "NoGuild": "Enable the selected guild expeditions, awakening, chaos-rift, crystal and personal-tree actions.",
        "GuardianTraining": "Train the guardian selected by its position in the roster.",
        "ChaosGuardianOrder": "Roster order for spending chaos-rift rewards during guardian visits and after successful guild chaos-rift hits.",
    }
    text = plain_help.get(key, OPTIONS[key].help)
    return (
        text.replace(f"settings.ini: {key}=0 when on.", "")
        .replace("Town > Oracle", "Oracle & blessings")
        .replace("Town > Guardian order", "Guardian training")
        .replace("Guild > Chaos rift", "Chaos rift")
        .strip()
    )


class AutomationEditor(ctk.CTkFrame):
    """One cached editor. Its controls keep using the window's live Binder."""

    def __init__(self, parent, ctx: PageContext, group: AutomationGroup, open_group):
        super().__init__(parent, fg_color="transparent")
        self.ctx = ctx
        self.group = group
        self.rows = {}
        self.composites = {}
        self._last_reasons: dict[str, str | None] = {}
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=f"{group.category.upper()}  /  {group.context.upper()}",
            text_color=theme.ACCENT,
            font=theme.font(11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(4, 6))
        ctk.CTkLabel(
            self,
            text=group.title,
            font=theme.heading(28),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(fill="x", padx=8)
        ctk.CTkLabel(
            self,
            text=group.summary,
            font=theme.font(13),
            text_color=theme.MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        ).pack(fill="x", padx=8, pady=(2, 16))
        self.card = card = Card(self, ctx, "Configuration")
        card.pack(fill="x", pady=(0, 10))
        self.lock_banner = card.banner("warn", "", visible=False)
        skipped = set()
        for key in group.keys:
            if key in skipped:
                continue
            if key in HERO_TARGET_KEYS:
                grid = CheckGrid(
                    card.body,
                    ctx,
                    [(k, OPTIONS[k].label) for k in HERO_TARGET_KEYS],
                    columns=2,
                    heading="Upgrade targets",
                )
                card.add(grid)
                self.composites["heroes"] = (grid, tuple(HERO_TARGET_KEYS))
                skipped.update(HERO_TARGET_KEYS)
            elif key in TREE_KEYS:
                for title, keys in TREE_GROUPS.items():
                    grid = CheckGrid(
                        card.body,
                        ctx,
                        [(k, OPTIONS[k].label) for k in keys],
                        columns=2,
                        heading=title,
                    )
                    card.add(grid, pady=(10, 4))
                    self.composites[title] = (grid, tuple(keys))
                skipped.update(TREE_KEYS)
            elif key in SELL_KEYS:
                row = card.row(
                    "Selling strategy",
                    "Choose the exotic items the bot should sell.",
                    lambda p: RadioGroup(p, ctx, SELL_KEYS, SELL_LABELS),
                )
                self.composites["selling"] = (row, tuple(SELL_KEYS))
                skipped.update(SELL_KEYS)
            elif key in PRIORITY_KEYS:
                ordered = OrderedList(
                    card.body,
                    ctx,
                    PRIORITY_CHOICES,
                    keys=PRIORITY_KEYS,
                    row_labels=["1st", "2nd", "3rd", "4th", "5th"],
                )
                card.note("Mission category priority · first filled at the top")
                card.add(ordered)
                self.composites["priority"] = (ordered, tuple(PRIORITY_KEYS))
                (self.reset_order_button,) = card.buttons(
                    (
                        "Reset category order",
                        lambda ordered=ordered: ordered.reset(
                            [SETTINGS_MAP[k][1] for k in PRIORITY_KEYS]
                        ),
                    )
                )
                skipped.update(PRIORITY_KEYS)
            elif key == "ChaosGuardianOrder":
                card.note("Chaos-rift upgrade order · first upgraded at the top")
                ordered = OrderedList(
                    card.body,
                    ctx,
                    CHAOS_GUARDIAN_CHOICES,
                    key=key,
                    display=OPTIONS[key].display,
                )
                card.add(ordered)
                self.composites["guardian_order"] = (ordered, (key,))
            else:
                row = card.option(key)
                row.default_help = _help_text(key)
                row.set_note(None, None)
                self.rows[key] = row
        note = EDITOR_NOTES.get(group.id)
        if note:
            card.note(note)
        self.selection_count = None
        if group.id in ("tree", "heroes"):
            self.selection_count = card.note("")
        self.daily_state = card.note("") if group.id == "arena" else None
        related = RELATED_GROUPS.get(group.id, ())
        if related:
            links = ctk.CTkFrame(self, fg_color="transparent")
            links.pack(fill="x", pady=(0, 8))
            for i, (title, target) in enumerate(related):
                ctk.CTkButton(
                    links,
                    text=f"{title}  →",
                    command=lambda target=target: open_group(target),
                    height=28,
                    fg_color=theme.SURFACE_ALT,
                    hover_color=theme.BORDER,
                    text_color=theme.TEXT,
                    font=theme.font(12),
                    anchor="w",
                ).grid(row=i, column=0, sticky="ew", pady=3)
            links.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text="Changes apply immediately. Disk saves wait until the bot stops.",
            font=theme.font(11),
            text_color=theme.MUTED,
            justify="left",
            anchor="w",
            wraplength=520,
        ).pack(fill="x", padx=8, pady=(4, 12))

    def refresh(self, progress: Progress) -> None:
        settings = self.ctx.settings
        group = self.group
        reasons = {key: disabled_reason(settings, group, key, progress) for key in group.keys}
        for key, row in self.rows.items():
            if key not in self._last_reasons or reasons[key] != self._last_reasons[key]:
                row.set_enabled(reasons[key] is None)
                # Validation/unknown-value notes still win while the control is editable.
                if reasons[key]:
                    row.set_note("muted", reasons[key])
                elif row.control.note:
                    row.set_note(*row.control.note)
                else:
                    row.set_note(None, None)
            if key in COUNTERS:
                counter, label = COUNTERS[key]
                row.control.set_live(f"{daily._int(settings, counter)} {label}")
        for name, (control, keys) in self.composites.items():
            enabled = all(reasons[key] is None for key in keys)
            if any(
                key not in self._last_reasons or reasons[key] != self._last_reasons[key]
                for key in keys
            ):
                control.set_enabled(enabled)
            if name == "priority":
                state = "normal" if enabled else "disabled"
                if self.reset_order_button.cget("state") != state:
                    self.reset_order_button.configure(state=state)
        self._last_reasons = reasons
        reason = progress.locked_reason(group.feature) if group.feature else None
        self.lock_banner.set_visible(bool(reason))
        if reason:
            self.lock_banner.set_text(
                f"This automation {reason}. Your choices stay saved and apply when unlocked."
            )
        if self.selection_count:
            keys = TREE_KEYS if group.id == "tree" else HERO_TARGET_KEYS
            text = f"{sum(settings.flag(key) for key in keys)} of {len(keys)} targets selected"
            if self.selection_count.cget("text") != text:
                self.selection_count.configure(text=text)
        if self.daily_state:
            text = (
                "Arena battles completed for this game day."
                if daily.arena_done(settings)
                else "Arena battles have not been marked complete for this game day."
            )
            if self.daily_state.cget("text") != text:
                self.daily_state.configure(text=text)


class AutomationsPage(ctk.CTkFrame):
    def __init__(self, parent, ctx: PageContext):
        super().__init__(parent, fg_color=theme.PAPER, corner_radius=0)
        self.ctx = ctx
        self.editors: dict[str, AutomationEditor] = {}
        self._traces = []
        self._pending = None
        self._reveal_after = None
        self._disposed = False
        self._progress = Progress()
        self._progress_stamp = object()
        self._button_styles: dict[str, bool] = {}
        self._unsubscribers: list[Callable[[], None]] = []
        self.state = getattr(ctx.window, "gui_state", ctx.extras)
        selected = str(self.state.get("automation_group", "alchemy"))
        self.selected = selected if selected in {g.id for g in AUTOMATIONS} else "alchemy"
        category = self.state.get("automation_category", "Develop")
        self.category = category if category in CATEGORIES else "All"
        # Older versions saved a local query; it must not become an invisible filter.
        self.state.pop("automation_query", None)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 12))
        heading.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            heading,
            text="Make room for adventure.",
            font=theme.heading(32),
            text_color=theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            heading,
            text="Choose what the bot takes care of, one automation at a time.",
            font=theme.font(13),
            text_color=theme.MUTED,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 12))
        self.filter_buttons = {}
        for i, category in enumerate(CATEGORIES):
            button = ctk.CTkButton(
                filters,
                text=category,
                width=100 if category == "Expeditions" else 80,
                height=32,
                font=theme.font(12),
                command=lambda c=category: self.set_category(c),
            )
            button.grid(row=0, column=i, padx=(0, 6))
            self.filter_buttons[category] = button
        filters.grid_columnconfigure(len(CATEGORIES), weight=1)
        self.result_count = ctk.CTkLabel(
            filters, text="", font=theme.font(11), text_color=theme.MUTED
        )
        self.result_count.grid(row=0, column=len(CATEGORIES), sticky="e")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 22))
        body.grid_columnconfigure(0, weight=0, minsize=260)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.library = ScrollableFrame(
            body,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=12,
            width=244,
        )
        self.library.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.library.grid_columnconfigure(0, weight=1)
        bind_platform_wheel(self.library)
        self.group_buttons = {}
        for i, group in enumerate(AUTOMATIONS):
            button = ctk.CTkButton(
                self.library,
                text=group.title,
                anchor="w",
                font=theme.font(13),
                height=65,
                corner_radius=7,
                command=lambda g=group.id: self.open_group(g, reveal=False),
            )
            button.grid(row=i, column=0, sticky="ew", padx=6, pady=(3, 4))
            button._text_label.configure(justify="left")
            self.group_buttons[group.id] = button
        self.empty_label = ctk.CTkLabel(
            self.library,
            text="No automations in this category.",
            text_color=theme.MUTED,
            font=theme.font(12),
            justify="left",
            wraplength=210,
        )
        self.inspector = ScrollableFrame(body, fg_color="transparent", corner_radius=0)
        self.inspector.grid(row=0, column=1, sticky="nsew")
        self.inspector.grid_columnconfigure(0, weight=1)
        bind_platform_wheel(self.inspector)
        self.empty_inspector = ctk.CTkLabel(
            self.inspector,
            text="Choose an automation from the library.",
            text_color=theme.MUTED,
            font=theme.heading(24),
        )
        for group in AUTOMATIONS:
            ctx.binder.register(*group.keys)
            for key in group.keys:
                var = ctx.binder.var(key, key in INVERTED_KEYS)
                self._traces.append((var, var.trace_add("write", self._queue_refresh)))
        cleanup = ctx.register_tick(self.refresh)
        if callable(cleanup):
            self._unsubscribers.append(cleanup)
        cleanup = ctx.binder.on_reload(self._queue_refresh)
        if callable(cleanup):
            self._unsubscribers.append(cleanup)
        ctx.extras["automations"] = self
        self.refresh()
        self._filter()

    def set_category(self, category: str) -> None:
        self.category = category if category in CATEGORIES else "All"
        self.state["automation_category"] = self.category
        self._filter()

    def _filter(self) -> None:
        if self._reveal_after is not None:
            self.after_cancel(self._reveal_after)
            self._reveal_after = None
        visible = []
        for group in AUTOMATIONS:
            button = self.group_buttons[group.id]
            if matches_group(group, "", self.category):
                button.grid()
                visible.append(group.id)
            else:
                button.grid_remove()
        for category, button in self.filter_buttons.items():
            selected = category == self.category
            button.configure(
                fg_color=theme.HEADER if selected else theme.SURFACE,
                hover_color=theme.HEADER if selected else theme.SURFACE_ALT,
                text_color=theme.ON_HEADER if selected else theme.TEXT,
                border_width=0 if selected else 1,
                border_color=theme.BORDER,
            )
        self.result_count.configure(text=f"{len(visible)} / {len(AUTOMATIONS)} automations")
        if visible:
            self.empty_label.grid_remove()
            self.empty_inspector.grid_remove()
            self.open_group(self.selected if self.selected in visible else visible[0], reveal=False)
        else:
            self.empty_label.grid(row=len(AUTOMATIONS), column=0, sticky="ew", padx=12, pady=24)
            for editor in self.editors.values():
                editor.grid_remove()
            self.empty_inspector.grid(row=0, column=0, sticky="w", padx=16, pady=30)
        self.library._parent_canvas.yview_moveto(0)

    def open_group(self, group_id: str, reveal: bool = True) -> None:
        if group_id not in self.group_buttons:
            return
        if reveal and not matches_group(GROUPS_BY_ID[group_id], "", self.category):
            self.selected = group_id
            self.category = "All"
            self.state["automation_category"] = self.category
            self._filter()
        previous = self.selected
        self.selected = group_id
        self.state["automation_group"] = group_id
        for name, editor in self.editors.items():
            if name != group_id:
                editor.grid_remove()
        if group_id not in self.editors:
            self.editors[group_id] = AutomationEditor(
                self.inspector,
                self.ctx,
                GROUPS_BY_ID[group_id],
                self.open_group,
            )
        self.empty_inspector.grid_remove()
        self.editors[group_id].grid(row=0, column=0, sticky="new", padx=(4, 8), pady=4)
        self.editors[group_id].refresh(self._progress)
        if previous != group_id:
            self.inspector._parent_canvas.yview_moveto(0)
        self._refresh_buttons()
        if reveal:
            if self._reveal_after is not None:
                self.after_cancel(self._reveal_after)
            self._reveal_after = self.after(25, self._reveal_selected)

    def reveal_target(self, key: str) -> bool:
        """Reveal an option or button without changing a value or running its command."""
        group = next((group for group in AUTOMATIONS if key in group.keys), None)
        if group is None:
            if key in self.group_buttons:
                self.open_group(key)
                reveal_widget(self.inspector, self.editors[key])
                return True
            if key == "reset_category_order":
                self.open_group("map")
                reveal_widget(self.inspector, self.editors["map"].reset_order_button)
                return True
            composite_name, separator, action = key.rpartition(":")
            if separator and action in ("all", "none"):
                group_id = "heroes" if composite_name == "heroes" else "tree"
                self.open_group(group_id)
                composite = self.editors[group_id].composites.get(composite_name)
                if composite and isinstance(composite[0], CheckGrid):
                    link = next(
                        link.widget
                        for link in composite[0].links
                        if link.widget.cget("text").casefold() == action
                    )
                    reveal_widget(self.inspector, link)
                    return True
            return False
        self.open_group(group.id)
        editor = self.editors[group.id]
        if key in editor.rows:
            target = editor.rows[key].widget
        else:
            composite, keys = next(
                (control, keys) for control, keys in editor.composites.values() if key in keys
            )
            if isinstance(composite, CheckGrid):
                target = composite.checks[keys.index(key)].widget
            elif isinstance(composite, OrderedList):
                target = composite.labels[keys.index(key)] if composite.keys else composite.widget
            else:
                target = composite.control.buttons[keys.index(key)]
        reveal_widget(self.inspector, target)
        return True

    def _reveal_selected(self) -> None:
        """Keep a linked editor's selected entry visible in the action library."""
        self._reveal_after = None
        button = self.group_buttons[self.selected]
        canvas = self.library._parent_canvas
        region = canvas.bbox("all")
        if not region or not button.winfo_ismapped():
            return
        height = region[3] - region[1]
        top = canvas.canvasy(0)
        y = button.winfo_y()
        if y < top:
            canvas.yview_moveto(y / max(1, height))
        elif y + button.winfo_height() > top + canvas.winfo_height():
            canvas.yview_moveto(
                (y + button.winfo_height() - canvas.winfo_height()) / max(1, height)
            )

    def _refresh_buttons(self) -> None:
        for group in AUTOMATIONS:
            selected = group.id == self.selected
            button = self.group_buttons[group.id]
            label = f"{group.title}\n{group.context} · {group_status(self.ctx.settings, group, self._progress)}"
            if button.cget("text") != label:
                button.configure(text=label)
            if self._button_styles.get(group.id) != selected:
                self._button_styles[group.id] = selected
                button.configure(
                    fg_color=theme.HEADER if selected else "transparent",
                    hover_color=theme.HEADER if selected else theme.SURFACE_ALT,
                    text_color=theme.ON_HEADER if selected else theme.TEXT,
                )

    def _queue_refresh(self, *_):
        if not self._disposed and self._pending is None:
            self._pending = self.after_idle(self._refresh_queued)

    def _refresh_queued(self):
        self._pending = None
        self.refresh()

    def refresh(self) -> None:
        if self._disposed:
            return
        path = os.path.join(self.ctx.base_dir, "progress.json")
        try:
            stamp = os.stat(path).st_mtime_ns
        except OSError:
            stamp = None
        if stamp != self._progress_stamp:
            self._progress_stamp = stamp
            self._progress = Progress.load(path)
        for editor in self.editors.values():
            editor.refresh(self._progress)
        self._refresh_buttons()

    def destroy(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._reveal_after is not None:
            self.after_cancel(self._reveal_after)
            self._reveal_after = None
        if self._pending is not None:
            self.after_cancel(self._pending)
            self._pending = None
        for var, token in self._traces:
            var.trace_remove("write", token)
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        if self.ctx.extras.get("automations") is self:
            self.ctx.extras.pop("automations", None)
        super().destroy()


def build(parent, ctx: PageContext):
    return AutomationsPage(parent, ctx)
