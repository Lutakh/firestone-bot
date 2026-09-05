# macOS port brief

Owner request (2026-09-05): run the bot on a Mac. This file is the brief for the session that
does the port. Everything in the repository stays in English; the owner chats in French.

## What is platform-specific today

Only `firestone_bot/platform/` and the launch/build glue depend on Windows:

| Module | Windows implementation | macOS equivalent |
|---|---|---|
| `platform/window.py` | Win32 via ctypes: find the game window (by process name/exe), client rect, activate/restore, minimised state | Quartz `CGWindowListCopyWindowInfo` (kCGWindowOwnerName/kCGWindowBounds) via pyobjc, activation with `NSRunningApplication.activateWithOptions_`, un-minimise via AppleScript / Accessibility API |
| `platform/dpi.py` | Per-monitor DPI awareness | no-op on macOS, but Retina must be handled: mss returns physical pixels (2x), Quartz bounds and pynput use points. Keep one convention: window rect in points, capture scale factor = image width / rect width, and convert screen click targets accordingly |
| `platform/process.py` | psutil process lookup, Steam/Epic launch (`steam://`, Epic URI), Steam library paths from the registry | psutil works; launch via `open steam://rungameid/<id>`; Epic is probably absent on macOS; check the game is available on the Mac Steam client first |
| `platform/capture.py` | mss | mss works (needs the Screen Recording permission) |
| `platform/input.py` | pynput (SendInput) | pynput works (needs the Accessibility permission); the `injected` flag used by the mouse-usage backlog item does not exist on macOS |
| `app.py` `_raise_window` / `present` | Win32 SetForegroundWindow | `NSApplication.activateIgnoringOtherApps_` or tkinter `lift` + `attributes('-topmost')` |
| `tools/build_exe.py`, `firestone-bot.spec` | one-dir exe + splash | PyInstaller `.app` bundle (no Splash on macOS), or a plain `python -m firestone_bot` launcher script for the first iteration |
| `features/game_launch.py` | uses process.py | unchanged once process.py is ported |

Everything else (features, atlas, viewport, GUI, settings, runner) is pure Python and must not
need changes.

## Coordinate model: resolution independent, to be VALIDATED not remeasured

All atlas entries are logical coordinates in the reference frame REF=(0,31,1920,1009) mapped
through `vision/viewport.py`: `scale = min(w/1920, h/1080)` of the client area, per-entry
anchors (HUD corners, centred dialogs and world map). Validated live at 1920x1009 and 1280x720
on Windows. On the Mac the work is: (1) get the client rect and the capture in the same unit,
(2) run `python -m firestone_bot.tools.measure_reference` / `probe_check` / `run_feature` at the
Mac window size and confirm the probes hit, (3) fix the viewport only if a systematic offset
shows up (title bar height, menu bar, Retina factor). Do not add Mac-specific atlas entries.

## Plan

1. `git clone https://github.com/Lutakh/firestone-bot.git`, branch `python-rework`, Python 3.12
   venv, `pip install -e .[dev]`, `ruff check .`, `pytest -q` (51 tests must pass unchanged).
2. Read `CLAUDE.md`, `docs/PYTHON_REWORK_PLAN.md` (architecture), `docs/PARITY.md`,
   `docs/MEASUREMENTS.md`, `README.md`.
3. Add a platform switch: keep `platform/window.py` etc. as the public API, move the Win32 code
   to `platform/win/` and add `platform/mac/`, selected on `sys.platform` at import time. CI on
   ubuntu imports the package headless: keep the lazy imports (pynput, pyobjc) behind functions.
4. Implement the Mac side (table above), then `tools/window_tool.py` and
   `tools/capture_tool.py` are the first live checks: window found, client rect, capture size,
   Retina factor.
5. Validate the coordinate model live (main screen probes, `run_feature check_mail`,
   `run_feature hero_upgrade`), then a dry-run cycle (`tools/dry_run.py`), then a real cycle
   from the GUI.
6. Packaging: `.app` via PyInstaller or a launcher script; document the two permissions
   (System Settings > Privacy & Security > Accessibility and Screen Recording) in README.
7. Update `docs/PARITY.md` (platform table), README (macOS section), `docs/BACKLOG.md`.

## Rules

- Never copy a settings.ini over the user's live one; never kill the owner's bot window.
- Commit messages in English, end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Keep the Windows build green: run the test-suite and `ruff` before each push; CI builds
  win/linux on every push.
