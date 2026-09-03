# Measurements

Facts measured on the owner's gaming machine. Updated as the plan (docs/PYTHON_REWORK_PLAN.md)
progresses. Captures live under `docs/captures/` (PNG, lossless, cropped to the game client area).

## Machine (2026-09-03)

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| Monitor | 1 x 1920x1080, primary, DPI 96 (100 %) |
| Taskbar | bottom, visible, 48 px (working area 1920x1032) |
| Python | 3.12.10 (winget `Python.Python.3.12`, user scope) in `python/.venv`; 3.13.7 also present |
| Game installs | Steam (`C:\Program Files (x86)\Steam\steamapps\common\Firestone`) and Epic (`C:\Program Files\Epic Games\FirestoneOnlineIdleRPG`) |
| Process name | `Firestone.exe` (same for both stores) |
| Window title | `Firestone` |

## 4.0 capture self-test

Game maximized (Epic build running). `capture_tool` reported, DPI mode `per-monitor-v2`:

| Rect | x | y | w | h |
|---|---|---|---|---|
| Window (outer, incl. invisible 8 px frame) | -8 | -8 | 1936 | 1048 |
| Client | 0 | 23 | 1920 | 1009 |

- Client size 1920x1009 matches the plan's expectation (`REF.w`, `REF.h`).
- Client top is y=23 here, not the y=31 the AHK numbers imply (Windows 10 with a 40 px taskbar:
  1080 - 40 - 1009 = 31). On this Windows 11 machine the taskbar is 48 px, so the maximized
  window is 8 px shorter in outer height and the client starts 8 px higher. The AHK coordinates
  (y 32..1039) therefore point 8 px too low on this machine; the viewport model (client rect
  measured live, logical frame `REF = (0, 31, 1920, 1009)`) absorbs this. To be confirmed by
  `tools/probe_check.py` in 4.1.
- Capture of the client rect renders correctly (BGRA from mss, converted to RGB for PNG).
