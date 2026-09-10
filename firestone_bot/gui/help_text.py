"""Static texts of the Help page (Tk-free)."""

from __future__ import annotations

HOME_SECTIONS: list[tuple[str, str]] = [
    (
        "System & game settings",
        (
            "- Use the Steam or Epic version (the browser version is not supported yet).\n"
            "- Reference setup: 1920x1080 monitor, 100 % DPI, game windowed and maximized, taskbar "
            "at the bottom. Other window sizes with the same aspect are supported; see the "
            "Camp's Environment card.\n"
            "- Game Settings (top right): NOT fullscreen. Game language: English."
        ),
    ),
    (
        "macOS",
        (
            "- First launch of a downloaded FirestoneBot.app: macOS says it could not verify it; "
            "click Done, then System Settings > Privacy & Security > Security > Open Anyway "
            "(once). The app is signed by the project, not notarised by Apple.\n"
            "- Game Settings > Graphics: turn Fullscreen OFF (the fullscreen Space letterboxes "
            "the game and hides the menu bar; a zoomed window is the reference setup). Keep "
            "the menu bar and the Dock visible, the bot measures the window.\n"
            "- System Settings > Privacy & Security: grant Screen Recording and Accessibility "
            "to FirestoneBot.app (or to the terminal app that runs the bot from source). "
            "Without Screen Recording every probe misses; without Accessibility no click "
            "reaches the game. Camp's Environment card names the missing one.\n"
            "- Retina displays are handled (captures in pixels, mouse in points).\n"
            "- Exit hotkey: Cmd + Esc."
        ),
    ),
    (
        "Gameplay settings",
        (
            "- Adventure button style: Mobile, PC or the new Adventure style (detected at each cycle).\n"
            '- Activate "Confirmation for purchase with jewels" (safety).'
        ),
    ),
    (
        "Bot usage",
        (
            "- Exit hotkey: Windows key + Esc (Cmd + Esc on macOS).\n"
            "- Review Automations and activate only what you need.\n"
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
    "Camp shows live session status, environment checks and daily quotas. "
    "Search above Camp Session to find settings, actions and information throughout the launcher. Automations groups actions into Collect, Develop, Expeditions and Trade. "
    "Journal shows the activity log. Workshop contains game setup, cycle behavior, files, "
    "appearance, updates and this help. Choose the interface skin after Workshop in the header.\n"
    "Locked features (engineer, arena, scarab, alchemist, oracle, guild buildings) are skipped "
    "until the account or guild level unlocks them; the levels are read on screen each cycle.\n"
    "Settings are saved automatically to settings.ini next to the executable (macOS: in "
    "~/Library/Application Support/FirestoneBot, see Workshop > Files & app)."
)

SHORTCUTS: list[tuple[str, str]] = [
    ("Win+Esc / Cmd+Esc", "Exit the bot (global hotkey, works while the game has the focus)"),
    ("F5", "Re-check the environment (game window, capture)"),
    ("Ctrl+S", "Save settings now"),
    ("Ctrl+5", "Choose the interface skin"),
    ("Ctrl+1 … Ctrl+4", "Open Camp, Automations, Journal or Workshop"),
    ("Ctrl+Q", "Exit"),
]
