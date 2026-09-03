# Firestone Bot

Automation bot for Firestone Idle RPG (Steam and Epic builds), written in Python 3.12. It is a
behaviour-for-behaviour port of the original AutoHotkey bot: same features, same
`settings.ini`, same screen-reading approach (pixel probes and simulated input, no memory
reading, no network calls to the game).

## Requirements

- Windows 10/11, Steam or Epic version of the game.
- Reference setup: 1920x1080 monitor, 100 % DPI, game windowed and maximized, taskbar at the
  bottom, game language English, adventure button style Mobile or PC. The Status panel on the
  Home tab reports the detected window, client size, scale and aspect. Any window with the
  reference aspect (1920:1009) maps exactly; 16:9 windows and fullscreen use per-widget anchors
  and are still being validated.
- Do not move or zoom the world map.
- The bot owns mouse and keyboard while it runs: the Unity client reads the real cursor, so
  the PC cannot be used for something else at the same time (see
  `docs/PYTHON_REWORK_PLAN.md` section 8 for the planned browser-based alternative).

## Install (packaged build)

Download `FirestoneBot-windows.zip` from the Releases page, unzip anywhere and run
`FirestoneBot.exe`. Put your existing `settings.ini` next to it (or start from
`settings.ini.example`). Settings are also editable in the GUI.

The executable is not code-signed: Windows SmartScreen shows "Windows protected your PC" the
first time; click "More info", then "Run anyway".

## Run from source

```bash
python -m venv .venv
.venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m firestone_bot
```

`settings.ini` and `MapStartState.ini` are read from the current directory (from the exe's
directory in the packaged build).

## Options added by the port

- **Heartbeat** (Settings tab): off by default. Sends progress messages to the maintainer's
  log server only when the toggle is on AND a Discord ID is set.
- **Safety cap** (Settings tab): 0 by default (identical to the AHK bot). The original has
  loops that wait forever for a screen change (arena battle, liberation mission, hero
  upgrades, main-menu finder); a cap of N stops such a loop after N iterations.
- **Dry run** (Home tab): runs a full cycle with mouse and keyboard disabled and logs every
  probe and click, to check the setup without touching the game.

## Tools

| Command | Purpose |
|---|---|
| `python -m firestone_bot.tools.capture_tool --out captures/x.png` | lossless capture of the game client + metadata |
| `python -m firestone_bot.tools.measure_reference` | window geometry, canvas scale |
| `python -m firestone_bot.tools.probe_check captures/x.png` | replay atlas probes on a capture |
| `python -m firestone_bot.tools.smoke_test --move 56,777` | find window, probe, move the mouse |
| `python -m firestone_bot.tools.run_feature check_mail [--dry-run --fast]` | run one feature module |
| `python -m firestone_bot.tools.dry_run [--live --cycles N]` | one full cycle, input disabled (or live) |
| `python -m firestone_bot.tools.window_tool --client 1280x720` | resize the game window for tests |

## Development

`ruff check .`, `pytest -q`, `pyinstaller firestone-bot.spec`. GitHub Actions runs the tests
and builds the Windows ZIP and Linux tarball on every push; tagged `v*` releases get the
archives attached. Plan, progress and measurements: `docs/`.
