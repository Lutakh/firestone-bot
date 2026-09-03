# Firestone Bot (Python port)

Python 3.12 port of the AutoHotkey bot in the repository root. Same features, same settings
file, same behaviour; runs on Windows (Steam and Epic builds) and, later, Linux.

## Run from source

```bash
cd python
python -m venv .venv
.venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m firestone_bot
```

`settings.ini` and `MapStartState.ini` are read from the current directory (from the exe's
directory in the packaged build). Existing files from the AHK bot work unchanged.

## Packaged build

GitHub Actions builds `FirestoneBot-windows.zip` (PyInstaller one-dir: `FirestoneBot.exe` +
`_internal/`) and `FirestoneBot-linux.tar.gz` on every push and attaches them to tagged
releases. Unzip anywhere and run `FirestoneBot.exe`.

The executable is not code-signed. Windows SmartScreen shows "Windows protected your PC" the
first time: click "More info", then "Run anyway". Some antivirus products flag PyInstaller
executables; the whole source is in this repository if you prefer to run from source.

## Requirements (unchanged from the AHK bot)

- Steam or Epic version, windowed and maximized on a 1920x1080 monitor at 100 % DPI, taskbar
  at the bottom. The Status panel on the Home tab reports the detected window, client size,
  scale and aspect. Any window with the reference aspect (1920:1009) maps exactly; 16:9
  windows and fullscreen rely on per-widget anchors and are still being validated.
- Game language English, adventure button style Mobile or PC.
- Do not move or zoom the world map.

## Background operation

The Steam/Epic client cannot be driven while you use the PC for something else: the Unity
player reads the real cursor and raw input, so the bot must own mouse and keyboard while it
runs. Running the browser version through the DevTools protocol (no OS cursor involved) is the
planned way to get background operation; see `docs/PYTHON_REWORK_PLAN.md` section 8.

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

## Layout

See `docs/PYTHON_REWORK_PLAN.md` section 3. Progress: `docs/PARITY.md`; measurements:
`docs/MEASUREMENTS.md`.
