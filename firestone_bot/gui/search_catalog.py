"""Launcher-wide, source-backed destinations. Searching never executes an action."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from firestone_bot.gui.automation_catalog import AUTOMATIONS, WORKSHOP_GROUPS
from firestone_bot.gui.catalog import OPTIONS, READ_ONLY_LABELS, TREE_GROUPS
from firestone_bot.gui.help_text import HOME_SECTIONS, SHORTCUTS, WHERE_THINGS_ARE


@dataclass(frozen=True)
class SearchResult:
    id: str
    title: str
    description: str
    page: str
    section: str = ""
    key: str = ""
    aliases: tuple[str, ...] = ()


def _target(page, section, key, title, description, *aliases, kind="action"):
    return SearchResult(f"{kind}:{page}:{key}", title, description, page, section, key, aliases)


# Stable keys also identify the real buttons retained by their destination view.
WORKSHOP_ACTIONS = (
    (
        "files",
        "check_update",
        "Check for updates now",
        "Check GitHub releases for a launcher update.",
        ("update", "updates", "launcher update", "application update", "software update"),
    ),
    (
        "files",
        "install_update",
        "Install available update",
        "Install the available launcher release while the bot is stopped.",
        ("download update", "upgrade launcher", "update installation"),
    ),
    (
        "files",
        "rollback",
        "Restore previous version",
        "Restore the previous application version when a backup is available.",
        ("rollback", "downgrade", "undo update"),
    ),
    (
        "files",
        "save",
        "Save settings now",
        "Write the current configuration to settings.ini.",
        ("save configuration", "Ctrl S"),
    ),
    (
        "files",
        "reload",
        "Reload settings from disk",
        "Read settings.ini again while the bot is stopped.",
        ("reload configuration",),
    ),
    (
        "files",
        "import",
        "Import settings from another folder",
        "Bring settings and map state from an older installation while stopped.",
        ("migrate", "import configuration"),
    ),
    (
        "files",
        "folder",
        "Open settings folder",
        "Show the application data directory containing settings and logs.",
        ("finder", "directory", "application support"),
    ),
    (
        "files",
        "log",
        "Open log file",
        "Open firestone-bot.log in the default application.",
        ("diagnostics file",),
    ),
    (
        "files",
        "reset",
        "Reset daily counters",
        "Clear today's usage counters and daily markers after confirmation, while stopped.",
        ("reset quotas", "reset arena", "reset mailbox", "reset chaos books"),
    ),
    (
        "files",
        "reset_statistics",
        "Reset cycle statistics",
        "Clear recorded cycle counts and durations after confirmation, while stopped.",
        ("clear statistics", "reset total time"),
    ),
    (
        "game",
        "environment",
        "Check environment",
        "Re-check the game window, capture and input permissions.",
        ("F5", "self test", "diagnostics"),
    ),
)

# Every read-only settings value displayed by the launcher has a searchable destination.
WORKSHOP_VALUES = (
    (
        "game",
        "LastPlatform",
        "Store seen last",
        "The game platform last recognized by the bot.",
        ("platform", "Steam", "Epic"),
    ),
    (
        "heartbeat",
        "ClientID",
        "Client ID",
        "Generated heartbeat client identifier; includes Copy.",
        ("copy client id",),
    ),
    ("files", "settings.ini", "Settings file", "Location of settings.ini.", ("settings path",)),
    (
        "files",
        "MapStartState.ini",
        "Map state file",
        "Location of MapStartState.ini.",
        ("map state path",),
    ),
    (
        "files",
        "firestone-bot.log",
        "Log file location",
        "Location of firestone-bot.log.",
        ("log path",),
    ),
    (
        "files",
        "settings_encoding",
        "Settings encoding",
        "Encoding of the loaded settings file.",
        ("unicode", "utf"),
    ),
    (
        "files",
        "appearance",
        "Display mode",
        "Choose System, Light or Dark appearance for the current skin.",
        ("appearance", "light mode", "dark mode", "system theme"),
    ),
    (
        "files",
        "CyclesTotal",
        "Completed cycles",
        "All-time completed cycle count, retained between launches.",
        ("cycle statistics",),
    ),
    (
        "files",
        "LastCycleMs",
        "Last cycle duration",
        "Duration of the last completed cycle.",
        ("cycle statistics",),
    ),
    (
        "files",
        "average_cycle",
        "Average cycle duration",
        "Average time spent in completed cycles.",
        ("cycle statistics",),
    ),
    (
        "files",
        "CycleMsTotal",
        "Total time in cycles",
        "Total time spent inside completed cycles, retained between launches.",
        ("cycle statistics",),
    ),
    (
        "files",
        "ArenaDoneDaily",
        "Arena completed today",
        "Whether today's arena battles have been marked complete.",
        ("daily arena marker",),
    ),
    (
        "files",
        "ChaosBooksDaily",
        "Chaos books purchased today",
        "Whether chaos books have been purchased in this game day.",
        ("daily books marker",),
    ),
    (
        "files",
        "MailSweepDaily",
        "Mailbox swept today",
        "Whether read mail has been deleted in this game day.",
        ("daily mailbox marker",),
    ),
    *(
        (
            "files",
            key,
            READ_ONLY_LABELS[key],
            "Live counter or reset timestamp saved by the bot.",
            ("daily counters",),
        )
        for key in (
            "TokenCountDaily",
            "ChaosCountDaily",
            "ScarabCountDaily",
            "CrystalCountDaily",
            "LastTokenReset",
            "LastChaosReset",
        )
    ),
    (
        "help",
        "requirements",
        "System & game requirements",
        "Game setup, operating system permissions and troubleshooting.",
        (
            "permissions",
            "troubleshooting",
            "screen recording",
            "accessibility",
            "macOS",
            "Steam",
            "Epic",
        ),
    ),
    ("help", "navigation", "Find your way", WHERE_THINGS_ARE, ("navigation", "help", "guide")),
    (
        "help",
        "shortcuts",
        "Keyboard shortcuts",
        " ".join(f"{combo} {action}" for combo, action in SHORTCUTS),
        ("hotkeys", "keyboard commands"),
    ),
    (
        "help",
        "about",
        "About Firestone Bot",
        "Application, Python and customtkinter versions.",
        ("version", "about"),
    ),
)

# Root-owned destinations: Camp data, the command dock, the Skin menu and Journal toolbar.
ROOT_TARGETS = (
    _target(
        "automations",
        "alchemy",
        "",
        "Automations",
        "Browse the action library and edit automation settings.",
        "routines",
        kind="page",
    ),
    _target(
        "workshop",
        "session",
        "",
        "Workshop",
        "Run behavior, game setup, application files, updates and help.",
        kind="page",
    ),
    _target(
        "camp",
        "session",
        "session",
        "Camp session",
        "Live bot state, current activity and the last completed cycle.",
        "status",
        "activity",
        "running",
        kind="view",
    ),
    _target(
        "camp",
        "environment",
        "environment",
        "Game checks",
        "Game window, platform, client area, scale, DPI, capture and input.",
        "environment",
        "permissions",
        kind="view",
    ),
    _target(
        "camp",
        "environment",
        "game_uptime",
        "Game running time",
        "Elapsed game process time used by the periodic restart check.",
        "uptime",
        "game runtime",
        "restart timer",
        "elapsed",
        kind="value",
    ),
    _target(
        "camp",
        "today",
        "today",
        "Daily limits",
        "Tavern tokens, chaos hits, scarab plays, crystal hits, arena state and the last daily reset.",
        "quotas",
        "usage",
        kind="view",
    ),
    _target(
        "camp",
        "account",
        "account_level",
        "Account level",
        "Last account level read during a game visit.",
        "player level",
        kind="value",
    ),
    _target(
        "camp",
        "account",
        "guild_level",
        "Guild level",
        "Last guild level read during a guild visit.",
        kind="value",
    ),
    _target(
        "camp",
        "statistics",
        "statistics",
        "All-time cycle statistics",
        "Completed cycles, last cycle, average cycle and total cycle time.",
        "statistics",
        "totals",
        kind="view",
    ),
    _target(
        "camp",
        "dock",
        "start",
        "Start bot",
        "Begin automation with the current configuration.",
        "run",
        "launch automation",
    ),
    _target(
        "camp", "dock", "stop", "Stop bot", "Stop the current automation run.", "stop automation"
    ),
    _target(
        "camp",
        "dock",
        "dry_run",
        "Dry run",
        "Run the existing simulation without sending game input.",
        "simulation",
        "simulate",
        "test run",
    ),
    _target(
        "camp",
        "navigation",
        "skin",
        "Choose interface skin",
        "Select Fieldbook, Retro or Futuristic from the Skin menu.",
        "skin",
        "theme",
        "Fieldbook",
        "Retro",
        "Futuristic",
    ),
    _target(
        "journal",
        "journal",
        "journal",
        "Session journal",
        "Actual activity messages from the bot.",
        "logs",
        "errors",
        "messages",
        kind="view",
    ),
    _target(
        "journal",
        "journal",
        "read_error_log",
        "Read error log",
        "Review errors and activity in the session journal.",
        "crashed",
    ),
    _target(
        "journal",
        "toolbar",
        "copy",
        "Copy all log messages",
        "Copy the visible session log to the clipboard.",
        "copy all",
        "clipboard",
    ),
    _target(
        "journal",
        "toolbar",
        "open_log",
        "Open log file",
        "Open the saved firestone-bot.log file.",
        "journal file",
    ),
    _target(
        "journal",
        "toolbar",
        "clear",
        "Clear journal view",
        "Clear the in-memory log view without deleting the log file.",
        "clear log",
        "clear view",
    ),
    _target(
        "journal",
        "toolbar",
        "follow",
        "Follow latest messages",
        "Scroll the journal to the newest activity and keep following it.",
        "follow latest",
        "autoscroll",
    ),
)


def _build_targets() -> tuple[SearchResult, ...]:
    targets = [*ROOT_TARGETS]
    for page, groups in (("automations", AUTOMATIONS), ("workshop", WORKSHOP_GROUPS)):
        for group in groups:
            targets.append(
                _target(
                    page,
                    group.id,
                    group.id,
                    group.title,
                    group.summary,
                    group.context,
                    group.category,
                    *(("cycle settings",) if page == "workshop" and group.id == "session" else ()),
                    kind="view",
                )
            )
            for key in group.keys:
                option = OPTIONS[key]
                title = option.label.lstrip("⚠ ")
                if key.startswith("Priority"):
                    title = f"Mission category priority · {option.label}"
                elif key == "RestartGameTime":
                    title = "Game restart interval"
                targets.append(
                    SearchResult(
                        f"option:{key}",
                        title,
                        option.help,
                        page,
                        group.id,
                        key,
                        (
                            key,
                            group.title,
                            group.category,
                            group.context,
                            *option.values,
                            *option.display.values(),
                        ),
                    )
                )
    for section, key, title, description, aliases in WORKSHOP_ACTIONS:
        targets.append(_target("workshop", section, key, title, description, *aliases))
    for section, key, title, description, aliases in WORKSHOP_VALUES:
        targets.append(
            _target("workshop", section, key, title, description, *aliases, kind="value")
        )
    for title, body in HOME_SECTIONS:
        targets.append(_target("workshop", "help", f"help:{title}", title, body, kind="help"))
    for section, title in (("files", "Files & app"), ("help", "Help")):
        targets.append(
            _target("workshop", section, section, title, f"Open Workshop · {title}.", kind="view")
        )
    targets.append(
        _target(
            "automations",
            "map",
            "reset_category_order",
            "Reset category order",
            "Restore the map mission category priority to its defaults.",
            "reset mission priority",
        )
    )
    for section, groups in (("heroes", ("heroes",)), ("tree", tuple(TREE_GROUPS))):
        for group in groups:
            for action in ("all", "none"):
                targets.append(
                    _target(
                        "automations",
                        section,
                        f"{group}:{action}",
                        f"Select {action} · {'Hero upgrade targets' if group == 'heroes' else group}",
                        "Change the selection for this group of upgrade targets.",
                        section,
                        "select targets",
                    )
                )
    return tuple(targets)


SEARCH_TARGETS = _build_targets()
TARGETS_BY_ID = {target.id: target for target in SEARCH_TARGETS}


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def search_launcher(query: str, *, limit: int | None = 30) -> list[SearchResult]:
    """Match every query word, prioritizing exact names and keys over incidental help."""
    query = _normalize(query)
    if not query or (limit is not None and limit <= 0):
        return []
    words = query.split()
    matches = []
    for index, target in enumerate(SEARCH_TARGETS):
        title, key = _normalize(target.title), _normalize(target.key)
        aliases = tuple(_normalize(alias) for alias in target.aliases)
        direct = " ".join((title, key, *aliases))
        corpus = " ".join((direct, _normalize(target.description), target.page, target.section))
        if not all(word in corpus for word in words):
            continue
        if query == key:
            score = 1200
        elif query == title:
            score = 1100
        elif query in aliases:
            score = 1000
        elif title.startswith(query):
            score = 800
        elif all(word in title for word in words):
            score = 700
        elif all(word in direct for word in words):
            score = 500
        else:
            score = 100
        matches.append((-score, index, target))
    matches.sort(key=lambda match: match[:2])
    results = [target for _, _, target in matches]
    return results if limit is None else results[:limit]
