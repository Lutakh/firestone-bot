"""Static texts of the Help page (Tk-free)."""

from __future__ import annotations

HOME_SECTIONS: list[tuple[str, str]] = [
    (
        "System & game settings",
        (
            "- Use the Steam or Epic version (the browser version is not supported yet).\n"
            "- Reference setup: 1920x1080 monitor, 100 % DPI, game windowed and maximized, taskbar "
            "at the bottom. Other window sizes with the same aspect are supported; see the "
            "Dashboard's Environment card.\n"
            "- Game Settings (top right): NOT fullscreen. Game language: English."
        ),
    ),
    (
        "Gameplay settings",
        (
            "- Adventure button style: Mobile or PC (NOT the new Adventure style).\n"
            '- Activate "Confirmation for purchase with jewels" (safety).'
        ),
    ),
    (
        "Bot usage",
        (
            "- Exit hotkey: Windows key + Esc.\n"
            "- Check all pages and activate ONLY what you need.\n"
            "- DO NOT move or zoom the map. Leave it as it is on login. If moved, restart the game."
        ),
    ),
    (
        "Troubleshooting",
        "- If missions are not found: make sure the system language and fonts are English.",
    ),
]

HOME_TEXT = "\n\n".join(f"{title.upper()}:\n{body}" for title, body in HOME_SECTIONS)

WHERE_THINGS_ARE = (
    "Everyday switches: Main screen, Town, Guild & Tree, Missions & WM. "
    "Rare options: Advanced. Live status: Dashboard. "
    "Settings are saved automatically to settings.ini next to the executable."
)

SHORTCUTS: list[tuple[str, str]] = [
    ("Win+Esc", "Exit the bot (global hotkey, works while the game has the focus)"),
    ("F5", "Re-check the environment (game window, capture)"),
    ("Ctrl+S", "Save settings now"),
    ("Ctrl+1 … Ctrl+7", "Switch page (Dashboard … Help)"),
    ("Ctrl+Q", "Exit"),
]
